from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import SurveyResponseForm
from .models import AccessToken, Response


class SurveyView:
    """GET: display survey form; POST: save responses and mark token used."""

    @staticmethod
    def get(request, token):
        access_token = get_object_or_404(AccessToken, token=token)
        if access_token.used:
            return render(request, "survey/already_used.html", {"access_token": access_token})
        form = SurveyResponseForm(survey=access_token.survey)
        return render(request, "survey/survey_form.html", {
            "form": form,
            "access_token": access_token,
            "survey": access_token.survey,
        })

    @staticmethod
    def post(request, token):
        access_token = get_object_or_404(AccessToken, token=token)
        if access_token.used:
            return render(request, "survey/already_used.html", {"access_token": access_token})

        survey = access_token.survey
        form = SurveyResponseForm(survey=survey, data=request.POST)

        if not form.is_valid():
            return render(request, "survey/survey_form.html", {
                "form": form,
                "access_token": access_token,
                "survey": survey,
            })

        # Save a Response for each answered question
        for question in survey.questions.all():
            field_name = f"question_{question.id}"
            value = form.cleaned_data.get(field_name)
            if value:  # skip unanswered (required=False)
                Response.objects.create(
                    question=question,
                    access_token=access_token,
                    value=int(value),
                )

        # Mark token as used
        access_token.used = True
        access_token.save(update_fields=["used"])

        return redirect(reverse("survey:confirmation", kwargs={"token": token}))

    def __call__(self, request, token):
        if request.method == "POST":
            return self.post(request, token)
        return self.get(request, token)


survey_view = SurveyView()


def confirmation_view(request, token):
    """Display a confirmation message after a successful submission."""
    access_token = get_object_or_404(AccessToken, token=token)
    return render(request, "survey/confirmation.html", {"access_token": access_token})


@login_required
def results_view(request, token):
    """Display aggregated survey results. Login required."""
    access_token = get_object_or_404(AccessToken, token=token)
    survey = access_token.survey

    questions = survey.questions.all()

    counts = (
        Response.objects
        .filter(question__survey=survey)
        .values('question_id', 'value')
        .annotate(count=Count('id'))
    )

    result_map = {}
    for row in counts:
        result_map.setdefault(row['question_id'], {})[row['value']] = row['count']

    total_submissions = survey.tokens.filter(used=True).count()

    # Build rows: list of (question, [count_for_1, count_for_2, ..., count_for_5])
    rows = []
    for question in questions:
        q_counts = result_map.get(question.id, {})
        rows.append((question, [q_counts.get(v, 0) for v in range(1, 6)]))

    return render(request, "survey/results.html", {
        "survey": survey,
        "access_token": access_token,
        "questions": questions,
        "result_map": result_map,
        "rows": rows,
        "total_submissions": total_submissions,
    })
