"""
Management views for authenticated survey owners.
All views require login; ownership checks return HTTP 403.
URLs are rooted at /survey/manage/
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from survey.forms import QuestionForm, SurveyForm
from survey.models import AccessToken, Question, Survey


@login_required
def survey_list_view(request):
    """List all surveys owned by the current user with token statistics."""
    surveys = (
        Survey.objects.filter(owner=request.user)
        .annotate(
            token_count=Count('tokens'),
            used_token_count=Count('tokens', filter=Q(tokens__used=True)),
        )
        .order_by('-created_at')
    )
    return render(request, 'survey/manage/survey_list.html', {'surveys': surveys})


@login_required
def survey_create_view(request):
    """Create a new survey owned by the current user."""
    if request.method == 'POST':
        form = SurveyForm(request.POST)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.owner = request.user
            survey.save()
            return redirect(reverse('manage:survey_detail', kwargs={'pk': survey.pk}))
    else:
        form = SurveyForm()
    return render(request, 'survey/manage/survey_create.html', {'form': form})


@login_required
def survey_detail_view(request, pk):
    """Display a survey's questions and allow token issuance."""
    survey = get_object_or_404(Survey, pk=pk)
    if survey.owner != request.user:
        return HttpResponseForbidden()
    questions = survey.questions.all()
    return render(request, 'survey/manage/survey_detail.html', {
        'survey': survey,
        'questions': questions,
    })


@login_required
def question_add_view(request, pk):
    """Add a question to an owned survey."""
    survey = get_object_or_404(Survey, pk=pk)
    if survey.owner != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.survey = survey
            question.save()
            return redirect(reverse('manage:survey_detail', kwargs={'pk': survey.pk}))
    else:
        form = QuestionForm()
    return render(request, 'survey/manage/question_add.html', {
        'form': form,
        'survey': survey,
    })


@login_required
def token_create_view(request, pk):
    """Issue a new access token for an owned survey."""
    survey = get_object_or_404(Survey, pk=pk)
    if survey.owner != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        token = AccessToken.objects.create(survey=survey)
        return render(request, 'survey/manage/token_created.html', {
            'survey': survey,
            'token': token,
        })
    return redirect(reverse('manage:survey_detail', kwargs={'pk': survey.pk}))
