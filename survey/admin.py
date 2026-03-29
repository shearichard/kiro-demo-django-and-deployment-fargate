import secrets

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import AccessToken, Question, Survey


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ('text', 'order')
    ordering = ('order', 'id')


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('name', 'question_count', 'token_count')
    inlines = [QuestionInline]

    @admin.display(description='Questions')
    def question_count(self, obj):
        return obj.questions.count()

    @admin.display(description='Tokens')
    def token_count(self, obj):
        return obj.tokens.count()


def generate_tokens(modeladmin, request, queryset):
    """Bulk-create access tokens for the selected surveys."""
    count = int(request.POST.get('token_count', 10))
    tokens = []
    for survey in queryset:
        for _ in range(count):
            tokens.append(AccessToken(survey=survey, token=secrets.token_urlsafe(32)))
    AccessToken.objects.bulk_create(tokens)
    modeladmin.message_user(
        request,
        f"Created {len(tokens)} token(s) across {queryset.count()} survey(s).",
    )


generate_tokens.short_description = "Generate access tokens for selected surveys"


@admin.register(AccessToken)
class AccessTokenAdmin(admin.ModelAdmin):
    list_display = ('survey', 'token_preview', 'used', 'created_at')
    list_filter = ('survey', 'used')
    actions = [generate_tokens]

    @admin.display(description='Token')
    def token_preview(self, obj):
        return f"{obj.token[:12]}…"
