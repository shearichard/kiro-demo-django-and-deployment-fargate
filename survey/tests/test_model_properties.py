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


# ---------------------------------------------------------------------------
# Property 8: Valid unused token displays survey and all questions
# Feature: django-survey-app, Property 8: Valid unused token displays survey and all questions
# Validates: Requirements 4.1
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(
    survey_name=st.text(min_size=1, max_size=200),
    question_texts=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=10),
)
@settings(max_examples=100)
def test_valid_unused_token_get_displays_survey_and_questions(survey_name, question_texts):
    """For any survey with questions and a valid unused token, GET /survey/<token>/
    returns HTTP 200 and the response body contains the survey name and every question text."""
    import html
    import uuid
    from django.test import Client

    # Use unique survey name to avoid IntegrityError across examples
    unique_name = f"{survey_name[:100]}-{uuid.uuid4()}"

    survey = Survey.objects.create(name=unique_name)
    for i, text in enumerate(question_texts):
        Question.objects.create(survey=survey, text=text, order=i)
    access_token = AccessToken.objects.create(survey=survey, used=False)

    client = Client()
    response = client.get(f"/survey/{access_token.token}/")

    assert response.status_code == 200

    # Django templates auto-escape special chars; compare against escaped versions
    content = response.content.decode("utf-8")
    assert html.escape(unique_name) in content, f"Survey name not found in response: {unique_name!r}"
    for text in question_texts:
        assert html.escape(text) in content, f"Question text not found in response: {text!r}"


# ---------------------------------------------------------------------------
# Property 9: Used token shows already-completed message
# Feature: django-survey-app, Property 9: Used token shows already-completed message
# Validates: Requirements 4.2
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(
    survey_name=st.text(min_size=1, max_size=200),
    question_texts=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=10),
)
@settings(max_examples=100)
def test_used_token_get_shows_already_completed(survey_name, question_texts):
    """For any access token marked as used, GET /survey/<token>/ returns HTTP 200,
    contains the already-completed message, and contains no form submission element."""
    import uuid
    from django.test import Client

    # Use unique survey name to avoid IntegrityError across examples
    unique_name = f"{survey_name[:100]}-{uuid.uuid4()}"

    survey = Survey.objects.create(name=unique_name)
    for i, text in enumerate(question_texts):
        Question.objects.create(survey=survey, text=text, order=i)
    access_token = AccessToken.objects.create(survey=survey, used=True)

    client = Client()
    response = client.get(f"/survey/{access_token.token}/")

    assert response.status_code == 200

    content = response.content.decode("utf-8")

    # Already-completed message must be present
    assert "already" in content.lower(), "Already-completed message not found in response"

    # No form submission element should be present
    assert "<form" not in content.lower(), "Unexpected <form> element found in already-used response"
    assert 'type="submit"' not in content.lower(), "Unexpected submit button found in already-used response"


# ---------------------------------------------------------------------------
# Property 10: Non-existent token returns 404
# Feature: django-survey-app, Property 10: Non-existent token returns 404
# Validates: Requirements 4.3
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(
    token_string=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
        min_size=1,
        max_size=200,
    )
)
@settings(max_examples=100)
def test_nonexistent_token_returns_404(token_string):
    """For any URL-safe string that does not correspond to an existing access token,
    GET /survey/<string>/ should return HTTP 404."""
    from django.test import Client

    # Ensure the token does not exist in the database
    AccessToken.objects.filter(token=token_string).delete()

    client = Client()
    response = client.get(f"/survey/{token_string}/")

    assert response.status_code == 404, (
        f"Expected 404 for non-existent token {token_string!r}, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Property 11: Valid partial submission records responses and marks token used
# Feature: django-survey-app, Property 11: Valid partial submission records responses and marks token used
# Validates: Requirements 4.4, 4.5, 4.6
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(
    num_questions=st.integers(min_value=1, max_value=8),
    answer_indices=st.lists(st.integers(min_value=0, max_value=7), min_size=0, max_size=8, unique=True),
    values=st.lists(st.integers(min_value=1, max_value=5), min_size=0, max_size=8),
)
@settings(max_examples=200)
def test_valid_partial_submission_records_responses_and_marks_token_used(
    num_questions, answer_indices, values
):
    """For any valid unused token and any subset of questions with valid (1-5) values,
    a POST to /survey/<token>/ should persist exactly the submitted response values,
    mark the token as used, and redirect to the confirmation page.
    An empty submission (all questions skipped) should also succeed."""
    import uuid
    from django.test import Client

    unique_name = f"partial-sub-{uuid.uuid4()}"
    survey = Survey.objects.create(name=unique_name)

    questions = []
    for i in range(num_questions):
        q = Question.objects.create(survey=survey, text=f"Question {i}", order=i)
        questions.append(q)

    access_token = AccessToken.objects.create(survey=survey, used=False)

    # Build the subset of (question_index, value) pairs to submit
    # answer_indices may reference indices beyond num_questions — clamp to valid range
    valid_indices = [idx for idx in answer_indices if idx < num_questions]
    # Pair each valid index with a value (zip truncates to shorter list)
    answers = list(zip(valid_indices, values))

    # Build POST data
    post_data = {}
    expected = {}  # question_id -> value
    for idx, val in answers:
        q = questions[idx]
        post_data[f"question_{q.id}"] = str(val)
        expected[q.id] = val

    client = Client()
    response = client.post(f"/survey/{access_token.token}/", data=post_data)

    # Should redirect to confirmation page
    assert response.status_code == 302, (
        f"Expected redirect (302), got {response.status_code}"
    )
    from django.urls import reverse
    expected_url = reverse("survey:confirmation", kwargs={"token": access_token.token})
    assert response["Location"] == expected_url, (
        f"Expected redirect to {expected_url!r}, got {response['Location']!r}"
    )

    # Token must be marked as used
    access_token.refresh_from_db()
    assert access_token.used is True, "Token was not marked as used after submission"

    # Exactly the submitted responses must be persisted with correct values
    saved_responses = Response.objects.filter(access_token=access_token)
    assert saved_responses.count() == len(expected), (
        f"Expected {len(expected)} responses, found {saved_responses.count()}"
    )
    for resp in saved_responses:
        assert resp.question_id in expected, (
            f"Unexpected response for question {resp.question_id}"
        )
        assert resp.value == expected[resp.question_id], (
            f"Response value mismatch for question {resp.question_id}: "
            f"expected {expected[resp.question_id]}, got {resp.value}"
        )


@pytest.mark.django_db
def test_empty_submission_succeeds():
    """Submitting with no answers (all questions skipped) should succeed —
    partial responses (including zero answers) are permitted."""
    import uuid
    from django.test import Client
    from django.urls import reverse

    unique_name = f"empty-sub-{uuid.uuid4()}"
    survey = Survey.objects.create(name=unique_name)
    for i in range(3):
        Question.objects.create(survey=survey, text=f"Question {i}", order=i)

    access_token = AccessToken.objects.create(survey=survey, used=False)

    client = Client()
    response = client.post(f"/survey/{access_token.token}/", data={})

    assert response.status_code == 302, (
        f"Expected redirect (302) for empty submission, got {response.status_code}"
    )
    expected_url = reverse("survey:confirmation", kwargs={"token": access_token.token})
    assert response["Location"] == expected_url

    access_token.refresh_from_db()
    assert access_token.used is True

    assert Response.objects.filter(access_token=access_token).count() == 0


# ---------------------------------------------------------------------------
# Property 12: Out-of-range submission is rejected
# Feature: django-survey-app, Property 12: Out-of-range submission is rejected
# Validates: Requirements 4.8
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(
    num_questions=st.integers(min_value=1, max_value=5),
    out_of_range_value=st.integers().filter(lambda x: x < 1 or x > 5),
)
@settings(max_examples=200)
def test_out_of_range_submission_rejected(num_questions, out_of_range_value):
    """For any valid unused token and any response value outside [1, 5], a POST to
    /survey/<token>/ should return a form with validation errors, leave the token
    unused, and persist no responses."""
    import uuid
    from django.test import Client

    unique_name = f"oor-sub-{uuid.uuid4()}"
    survey = Survey.objects.create(name=unique_name)

    questions = []
    for i in range(num_questions):
        q = Question.objects.create(survey=survey, text=f"Question {i}", order=i)
        questions.append(q)

    access_token = AccessToken.objects.create(survey=survey, used=False)

    # POST with the out-of-range value for the first question
    post_data = {f"question_{questions[0].id}": str(out_of_range_value)}

    client = Client()
    response = client.post(f"/survey/{access_token.token}/", data=post_data)

    # Must NOT redirect — should re-render the form with errors
    assert response.status_code == 200, (
        f"Expected 200 (form re-render with errors) for out-of-range value "
        f"{out_of_range_value}, got {response.status_code}"
    )

    # Token must remain unused
    access_token.refresh_from_db()
    assert access_token.used is False, (
        f"Token was incorrectly marked as used after out-of-range submission "
        f"(value={out_of_range_value})"
    )

    # No responses should have been persisted
    assert Response.objects.filter(access_token=access_token).count() == 0, (
        f"Responses were persisted despite out-of-range value {out_of_range_value}"
    )


# ---------------------------------------------------------------------------
# Property 13: Results counts accuracy
# Feature: django-survey-app, Property 13: Results counts accuracy
# Validates: Requirements 5.2, 5.3, 5.4
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(
    num_questions=st.integers(min_value=1, max_value=5),
    submissions=st.lists(
        st.lists(st.integers(min_value=1, max_value=5), min_size=0, max_size=5),
        min_size=0,
        max_size=10,
    ),
)
@settings(max_examples=200, deadline=None)
# Feature: django-survey-app, Property 13: Results counts accuracy
def test_results_counts_accuracy(num_questions, submissions):
    """For any survey with any set of submissions, the results view must display,
    for each (question, value) pair, a count equal to the number of Response rows
    with that question and value. When no submissions exist, all counts are zero.
    The total submission count equals the number of tokens with used=True.

    **Validates: Requirements 5.2, 5.3, 5.4**
    """
    import uuid
    from collections import defaultdict

    from django.contrib.auth.models import User
    from django.test import Client

    unique_name = f"results-counts-{uuid.uuid4()}"
    survey = Survey.objects.create(name=unique_name)

    questions = []
    for i in range(num_questions):
        q = Question.objects.create(survey=survey, text=f"Question {i}", order=i)
        questions.append(q)

    # Build expected counts: {question_id: {value: count}}
    expected_counts = defaultdict(lambda: defaultdict(int))

    # Create submissions — each entry in `submissions` is a list of values (one per question)
    used_token_count = 0
    for sub_values in submissions:
        token = AccessToken.objects.create(survey=survey, used=True)
        used_token_count += 1
        for i, val in enumerate(sub_values):
            if i < num_questions:
                q = questions[i]
                Response.objects.create(question=q, access_token=token, value=val)
                expected_counts[q.id][val] += 1

    # Authenticate as a staff user to access the results view
    staff_user = User.objects.create_user(
        username=f"staff-{uuid.uuid4()}", password="pass", is_staff=True
    )
    client = Client()
    client.force_login(staff_user)

    # Use any token (or create one if none exist) to build the results URL
    any_token = AccessToken.objects.filter(survey=survey).first()
    if any_token is None:
        any_token = AccessToken.objects.create(survey=survey, used=False)

    response = client.get(f"/survey/{any_token.token}/results/")
    assert response.status_code == 200

    # Verify via the context rather than HTML parsing for precision
    result_map = response.context["result_map"]
    total_submissions = response.context["total_submissions"]

    # Req 5.3: total submission count equals number of used tokens
    assert total_submissions == used_token_count, (
        f"Expected total_submissions={used_token_count}, got {total_submissions}"
    )

    # Req 5.2 & 5.4: for each question and each value 1-5, count must match
    for q in questions:
        for val in range(1, 6):
            actual = result_map.get(q.id, {}).get(val, 0)
            expected = expected_counts[q.id][val]
            assert actual == expected, (
                f"Count mismatch for question {q.id}, value {val}: "
                f"expected {expected}, got {actual}"
            )
