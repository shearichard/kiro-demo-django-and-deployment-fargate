"""
Property-based tests for survey data models.
Uses Hypothesis + pytest-django.
"""
import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from hypothesis import given, settings
from hypothesis import strategies as st

from survey.models import AccessToken, Question, Response, Survey, generate_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_survey(name="Test Survey"):
    return Survey.objects.create(name=name)


def make_question(survey, text="Rate this", order=0):
    return Question.objects.create(survey=survey, text=text, order=order)


def make_token(survey):
    return AccessToken.objects.create(survey=survey)


# ---------------------------------------------------------------------------
# Property 1: Survey name uniqueness
# Feature: django-survey-app, Property 1: Survey name uniqueness
# Validates: Requirements 1.1
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(name=st.text(min_size=1, max_size=255))
@settings(max_examples=100)
def test_survey_name_uniqueness(name):
    """Two surveys with the same name: second creation must be rejected."""
    Survey.objects.all().delete()
    Survey.objects.create(name=name)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Survey.objects.create(name=name)


# ---------------------------------------------------------------------------
# Property 2: Survey update round-trip
# Feature: django-survey-app, Property 2: Survey update round-trip
# Validates: Requirements 1.2
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(
    original_name=st.text(min_size=1, max_size=255),
    new_name=st.text(min_size=1, max_size=255),
    new_desc=st.text(max_size=1000),
)
@settings(max_examples=100)
def test_survey_update_round_trip(original_name, new_name, new_desc):
    """Updating name/description and reading back returns exactly what was written."""
    Survey.objects.all().delete()
    survey = Survey.objects.create(name=original_name)
    survey.name = new_name
    survey.description = new_desc
    survey.save()

    refreshed = Survey.objects.get(pk=survey.pk)
    assert refreshed.name == new_name
    assert refreshed.description == new_desc


# ---------------------------------------------------------------------------
# Property 3: Survey cascade delete
# Feature: django-survey-app, Property 3: Survey cascade delete
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(n=st.integers(min_value=1, max_value=10))
@settings(max_examples=100)
def test_survey_cascade_delete(n):
    """Deleting a survey removes all its questions, tokens, and responses."""
    survey = Survey.objects.create(name=f"cascade-survey-{n}-{id(n)}")
    token = make_token(survey)
    for i in range(n):
        q = make_question(survey, text=f"Q{i}", order=i)
        Response.objects.create(question=q, access_token=token, value=1)

    survey_pk = survey.pk
    survey.delete()

    assert Question.objects.filter(survey_id=survey_pk).count() == 0
    assert AccessToken.objects.filter(survey_id=survey_pk).count() == 0
    assert Response.objects.filter(question__survey_id=survey_pk).count() == 0


# ---------------------------------------------------------------------------
# Property 4: Question blank text rejection
# Feature: django-survey-app, Property 4: Question blank text rejection
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
@given(blank_text=st.text(alphabet=" \t\n\r", max_size=50))
@settings(max_examples=100)
def test_question_blank_text_rejected(blank_text):
    """Questions with empty or whitespace-only text must fail validation."""
    import uuid
    survey = Survey.objects.create(name=f"blank-{uuid.uuid4()}")
    q = Question(survey=survey, text=blank_text)
    with pytest.raises(ValidationError):
        q.full_clean()
    assert Question.objects.filter(survey=survey).count() == 0
    survey.delete()


# ---------------------------------------------------------------------------
# Property 5: Response value range enforcement
# Feature: django-survey-app, Property 5: Response value range enforcement
# Validates: Requirements 2.3, 4.7, 4.8
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
@given(value=st.integers().filter(lambda x: x < 1 or x > 5))
@settings(max_examples=200)
def test_out_of_range_response_rejected(value):
    """Response values outside [1, 5] must be rejected by model validation."""
    survey = Survey.objects.create(name=f"range-out-{value}")
    token = AccessToken.objects.create(survey=survey)
    q = Question.objects.create(survey=survey, text="Rate this")
    r = Response(question=q, access_token=token, value=value)
    with pytest.raises(ValidationError):
        r.full_clean()
    survey.delete()


@pytest.mark.django_db
@given(value=st.integers(min_value=1, max_value=5))
@settings(max_examples=200)
def test_in_range_response_accepted(value):
    """Response values within [1, 5] must be accepted."""
    survey = make_survey(f"range-survey-in-{value}")
    token = make_token(survey)
    q = make_question(survey)
    r = Response(question=q, access_token=token, value=value)
    r.full_clean()  # must not raise
    r.save()
    assert Response.objects.filter(pk=r.pk).exists()


# ---------------------------------------------------------------------------
# Property 6: Question cascade delete
# Feature: django-survey-app, Property 6: Question cascade delete
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(n=st.integers(min_value=1, max_value=10))
@settings(max_examples=100)
def test_question_cascade_delete(n):
    """Deleting a question removes all its responses."""
    survey = make_survey(f"q-cascade-{n}-{id(n)}")
    token = make_token(survey)
    q = make_question(survey)
    # Create n tokens/responses (unique_together requires distinct tokens)
    for i in range(n):
        t = AccessToken.objects.create(survey=survey)
        Response.objects.create(question=q, access_token=t, value=(i % 5) + 1)

    q_pk = q.pk
    q.delete()

    assert Response.objects.filter(question_id=q_pk).count() == 0


# ---------------------------------------------------------------------------
# Property 7: Token length, URL-safety, and uniqueness
# Feature: django-survey-app, Property 7: Token length, URL-safety, and uniqueness
# Validates: Requirements 3.2, 3.3, 3.5
# ---------------------------------------------------------------------------

URL_SAFE_RE = re.compile(r'^[A-Za-z0-9_-]+$')


@given(n=st.integers(min_value=2, max_value=50))
@settings(max_examples=100)
def test_token_properties(n):
    """Generated tokens are ≥32 chars, URL-safe, and pairwise distinct."""
    tokens = [generate_token() for _ in range(n)]
    for t in tokens:
        assert len(t) >= 32, f"Token too short: {len(t)}"
        assert URL_SAFE_RE.match(t), f"Token not URL-safe: {t!r}"
    assert len(set(tokens)) == n, "Duplicate tokens generated"


@pytest.mark.django_db
def test_duplicate_token_rejected():
    """Inserting a duplicate token value must be rejected by the unique constraint."""
    survey = make_survey("dup-token-survey")
    token_val = generate_token()
    AccessToken.objects.create(survey=survey, token=token_val)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AccessToken.objects.create(survey=survey, token=token_val)
