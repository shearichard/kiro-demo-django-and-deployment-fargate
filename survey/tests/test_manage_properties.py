"""
Property-based tests for the survey user management feature.
Uses Hypothesis + pytest-django.

Each property is annotated with the requirement(s) it validates.
"""
import re
import string
import uuid

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from hypothesis import given, settings
from hypothesis import strategies as st

from survey.models import AccessToken, Question, Survey, generate_token


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Printable non-whitespace text — safe for Django CharField and our clean_name()
PRINTABLE_NON_WS = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Po", "Ps", "Pe", "Sm"),
        whitelist_characters="-_",
    ),
    min_size=1,
    max_size=200,
)

# Whitespace-only strings (including empty string)
WHITESPACE_ONLY = st.text(alphabet=string.whitespace, max_size=50)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username=None):
    """Create a fresh user with a unique username."""
    username = username or f"user-{uuid.uuid4()}"
    return User.objects.create_user(username=username, password="testpassword")


def make_survey(owner, name=None):
    """Create a survey owned by the given user."""
    name = name or f"survey-{uuid.uuid4()}"
    return Survey.objects.create(owner=owner, name=name)


# ---------------------------------------------------------------------------
# Property 1: Survey creation sets owner to current user
# Feature: survey-user-management, Property 1: Survey creation sets owner to current user
# Validates: Requirements 1.2, 2.1
# ---------------------------------------------------------------------------

SAFE_TEXT = st.text(
    alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)),
    max_size=500,
)


@pytest.mark.django_db
@given(name=PRINTABLE_NON_WS, description=SAFE_TEXT)
@settings(max_examples=50, deadline=None)
def test_survey_creation_sets_owner(name, description):
    """
    # Feature: survey-user-management, Property 1: Survey creation sets owner to current user

    For any authenticated user and any valid (non-empty, non-whitespace) survey
    name + description, submitting the create-survey form should persist a Survey
    whose owner equals the submitting user.

    **Validates: Requirements 1.2, 2.1**
    """
    unique_name = f"{name[:100]}-{uuid.uuid4()}"
    owner = make_user()

    client = Client()
    client.force_login(owner)

    url = reverse("manage:survey_create")
    response = client.post(url, {"name": unique_name, "description": description})

    assert response.status_code == 302, (
        f"Expected redirect (302) after valid survey creation, got {response.status_code}. "
        f"Form errors: {response.context['form'].errors if response.context else 'n/a'}"
    )

    survey = Survey.objects.get(name=unique_name)
    assert survey.owner == owner, (
        f"Expected survey.owner={owner!r}, got {survey.owner!r}"
    )


# ---------------------------------------------------------------------------
# Property 2: Owner cascade delete removes surveys
# Feature: survey-user-management, Property 2: Owner cascade delete removes surveys
# Validates: Requirements 1.3
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(n=st.integers(min_value=1, max_value=10))
@settings(max_examples=50, deadline=None)
def test_owner_cascade_delete_removes_surveys(n):
    """
    # Feature: survey-user-management, Property 2: Owner cascade delete removes surveys

    For any user who owns N surveys, deleting that user should result in all N of
    those surveys also being deleted from the database.

    **Validates: Requirements 1.3**
    """
    owner = make_user()
    survey_pks = []
    for i in range(n):
        s = Survey.objects.create(owner=owner, name=f"cascade-{i}-{uuid.uuid4()}")
        survey_pks.append(s.pk)

    owner_pk = owner.pk
    owner.delete()

    remaining = Survey.objects.filter(pk__in=survey_pks).count()
    assert remaining == 0, (
        f"Expected 0 surveys after cascade delete, found {remaining}"
    )


# ---------------------------------------------------------------------------
# Property 3: Whitespace-only name is rejected
# Feature: survey-user-management, Property 3: Whitespace-only name is rejected
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(blank_name=WHITESPACE_ONLY)
@settings(max_examples=50, deadline=None)
def test_whitespace_only_survey_name_rejected(blank_name):
    """
    # Feature: survey-user-management, Property 3: Whitespace-only name is rejected

    For any string composed entirely of whitespace characters (including the empty
    string), submitting it as a survey name should fail form validation and no new
    Survey should be created.

    **Validates: Requirements 2.3**
    """
    owner = make_user()
    initial_count = Survey.objects.count()

    client = Client()
    client.force_login(owner)

    url = reverse("manage:survey_create")
    response = client.post(url, {"name": blank_name, "description": ""})

    assert response.status_code == 200, (
        f"Expected 200 (form with errors) for blank name, got {response.status_code}"
    )
    assert Survey.objects.count() == initial_count, (
        "A survey was created despite whitespace-only name"
    )
    form = response.context["form"]
    assert form.errors, "Form should have validation errors for whitespace-only name"


# ---------------------------------------------------------------------------
# Property 4: Duplicate survey name is rejected
# Feature: survey-user-management, Property 4: Duplicate survey name is rejected
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(name=PRINTABLE_NON_WS)
@settings(max_examples=50, deadline=None)
def test_duplicate_survey_name_rejected(name):
    """
    # Feature: survey-user-management, Property 4: Duplicate survey name is rejected

    For any survey name that already exists in the database, submitting that same
    name in the create-survey form should fail validation and no new Survey should
    be created.

    **Validates: Requirements 2.4**
    """
    owner = make_user()
    # Use a unique suffix so we know exactly which name to test
    unique_name = f"{name[:100]}-{uuid.uuid4()}"
    Survey.objects.create(owner=owner, name=unique_name)

    client = Client()
    client.force_login(owner)

    url = reverse("manage:survey_create")
    response = client.post(url, {"name": unique_name, "description": ""})

    assert response.status_code == 200, (
        f"Expected 200 (form with errors) for duplicate name, got {response.status_code}"
    )
    assert Survey.objects.filter(name=unique_name).count() == 1, (
        "Duplicate survey was created despite uniqueness constraint"
    )
    form = response.context["form"]
    assert "name" in form.errors, (
        f"Expected 'name' field error for duplicate name, got: {form.errors}"
    )


# ---------------------------------------------------------------------------
# Property 5: Whitespace-only question text is rejected
# Feature: survey-user-management, Property 5: Whitespace-only question text is rejected
# Validates: Requirements 3.3
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(blank_text=WHITESPACE_ONLY)
@settings(max_examples=50, deadline=None)
def test_whitespace_only_question_text_rejected(blank_text):
    """
    # Feature: survey-user-management, Property 5: Whitespace-only question text is rejected

    For any string composed entirely of whitespace characters (including the empty
    string), submitting it as a question text should fail form validation and no
    new Question should be created.

    **Validates: Requirements 3.3**
    """
    owner = make_user()
    survey = make_survey(owner)
    initial_count = Question.objects.filter(survey=survey).count()

    client = Client()
    client.force_login(owner)

    url = reverse("manage:question_add", kwargs={"pk": survey.pk})
    response = client.post(url, {"text": blank_text, "order": 0})

    assert response.status_code == 200, (
        f"Expected 200 (form with errors) for blank question text, got {response.status_code}"
    )
    assert Question.objects.filter(survey=survey).count() == initial_count, (
        "A question was created despite whitespace-only text"
    )
    form = response.context["form"]
    assert form.errors, "Form should have validation errors for whitespace-only text"


# ---------------------------------------------------------------------------
# Property 6: Non-owner cannot add question (403)
# Feature: survey-user-management, Property 6: Non-owner cannot add question (403)
# Validates: Requirements 3.4
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(question_text=PRINTABLE_NON_WS)
@settings(max_examples=50, deadline=None)
def test_non_owner_cannot_add_question(question_text):
    """
    # Feature: survey-user-management, Property 6: Non-owner cannot add question (403)

    For any survey and any authenticated user who is not the survey's owner, a POST
    request to the add-question endpoint for that survey should return HTTP 403 and
    no new Question should be created.

    **Validates: Requirements 3.4**
    """
    owner = make_user()
    non_owner = make_user()
    survey = make_survey(owner)
    initial_count = Question.objects.filter(survey=survey).count()

    client = Client()
    client.force_login(non_owner)

    url = reverse("manage:question_add", kwargs={"pk": survey.pk})
    response = client.post(url, {"text": question_text, "order": 0})

    assert response.status_code == 403, (
        f"Expected 403 for non-owner adding question, got {response.status_code}"
    )
    assert Question.objects.filter(survey=survey).count() == initial_count, (
        "A question was created despite user not being the survey owner"
    )


# ---------------------------------------------------------------------------
# Property 7: Survey list is scoped to current user
# Feature: survey-user-management, Property 7: Survey list is scoped to current user
# Validates: Requirements 4.1
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(
    own_count=st.integers(min_value=1, max_value=10),
    other_count=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=50, deadline=None)
def test_survey_list_scoped_to_current_user(own_count, other_count):
    """
    # Feature: survey-user-management, Property 7: Survey list is scoped to current user

    For any authenticated user, the survey list view should return exactly the set
    of surveys owned by that user — no more, no fewer — regardless of how many
    surveys owned by other users exist in the database.

    **Validates: Requirements 4.1**
    """
    owner = make_user()
    other = make_user()

    own_pks = set()
    for _ in range(own_count):
        s = make_survey(owner)
        own_pks.add(s.pk)

    for _ in range(other_count):
        make_survey(other)

    client = Client()
    client.force_login(owner)

    url = reverse("manage:survey_list")
    response = client.get(url)

    assert response.status_code == 200
    surveys = list(response.context["surveys"])
    returned_pks = {s.pk for s in surveys}

    assert returned_pks == own_pks, (
        f"Survey list not scoped correctly. "
        f"Expected {own_pks}, got {returned_pks}."
    )


# ---------------------------------------------------------------------------
# Property 8: Token statistics are accurate per survey
# Feature: survey-user-management, Property 8: Token statistics are accurate per survey
# Validates: Requirements 4.3, 4.4
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(
    total=st.integers(min_value=0, max_value=50),
    used=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=50, deadline=None)
def test_token_statistics_accurate(total, used):
    """
    # Feature: survey-user-management, Property 8: Token statistics are accurate per survey

    For any survey with T total tokens and U used tokens (0 ≤ U ≤ T), the survey
    list view context should expose token_count = T and used_token_count = U for
    that survey.

    **Validates: Requirements 4.3, 4.4**
    """
    actual_used = min(used, total)

    owner = make_user()
    survey = make_survey(owner)

    for _ in range(actual_used):
        AccessToken.objects.create(survey=survey, used=True)
    for _ in range(total - actual_used):
        AccessToken.objects.create(survey=survey, used=False)

    client = Client()
    client.force_login(owner)

    url = reverse("manage:survey_list")
    response = client.get(url)

    assert response.status_code == 200
    surveys = list(response.context["surveys"])
    assert len(surveys) == 1

    s = surveys[0]
    assert s.token_count == total, (
        f"Expected token_count={total}, got {s.token_count}"
    )
    assert s.used_token_count == actual_used, (
        f"Expected used_token_count={actual_used}, got {s.used_token_count}"
    )


# ---------------------------------------------------------------------------
# Property 9: Non-owner cannot create token (403)
# Feature: survey-user-management, Property 9: Non-owner cannot create token (403)
# Validates: Requirements 5.3
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(st.integers(min_value=0, max_value=5))  # token pre-count varies the state slightly
@settings(max_examples=50, deadline=None)
def test_non_owner_cannot_create_token(pre_existing_tokens):
    """
    # Feature: survey-user-management, Property 9: Non-owner cannot create token (403)

    For any survey and any authenticated user who is not the survey's owner, a POST
    request to the token-create endpoint should return HTTP 403 and no new
    AccessToken should be created.

    **Validates: Requirements 5.3**
    """
    owner = make_user()
    non_owner = make_user()
    survey = make_survey(owner)

    for _ in range(pre_existing_tokens):
        AccessToken.objects.create(survey=survey)
    initial_count = AccessToken.objects.filter(survey=survey).count()

    client = Client()
    client.force_login(non_owner)

    url = reverse("manage:token_create", kwargs={"pk": survey.pk})
    response = client.post(url)

    assert response.status_code == 403, (
        f"Expected 403 for non-owner creating token, got {response.status_code}"
    )
    assert AccessToken.objects.filter(survey=survey).count() == initial_count, (
        "A token was created despite user not being the survey owner"
    )


# ---------------------------------------------------------------------------
# Property 10: Generated tokens are URL-safe and at least 32 characters
# Feature: survey-user-management, Property 10: Generated tokens are URL-safe and at least 32 characters
# Validates: Requirements 5.5
# ---------------------------------------------------------------------------

URL_SAFE_RE = re.compile(r'^[A-Za-z0-9_-]+$')


@given(n=st.integers(min_value=1, max_value=50))
@settings(max_examples=100)
def test_generated_tokens_url_safe_and_min_length(n):
    """
    # Feature: survey-user-management, Property 10: Generated tokens are URL-safe and at least 32 characters

    For any call to generate_token(), the returned string should have length ≥ 32
    and contain only URL-safe characters (alphanumeric characters, '-', '_').

    **Validates: Requirements 5.5**
    """
    for _ in range(n):
        token = generate_token()
        assert len(token) >= 32, (
            f"Token too short: length={len(token)}, token={token!r}"
        )
        assert URL_SAFE_RE.match(token), (
            f"Token contains non-URL-safe characters: {token!r}"
        )


# ---------------------------------------------------------------------------
# Property 11: Non-owner cannot view survey detail (403)
# Feature: survey-user-management, Property 11: Non-owner cannot view survey detail (403)
# Validates: Requirements 6.3
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@given(st.integers(min_value=0, max_value=5))  # question pre-count varies the state slightly
@settings(max_examples=50, deadline=None)
def test_non_owner_cannot_view_survey_detail(pre_existing_questions):
    """
    # Feature: survey-user-management, Property 11: Non-owner cannot view survey detail (403)

    For any survey and any authenticated user who is not the survey's owner, a GET
    request to the survey detail endpoint should return HTTP 403.

    **Validates: Requirements 6.3**
    """
    owner = make_user()
    non_owner = make_user()
    survey = make_survey(owner)

    for i in range(pre_existing_questions):
        Question.objects.create(survey=survey, text=f"Q{i}", order=i)

    client = Client()
    client.force_login(non_owner)

    url = reverse("manage:survey_detail", kwargs={"pk": survey.pk})
    response = client.get(url)

    assert response.status_code == 403, (
        f"Expected 403 for non-owner viewing survey detail, got {response.status_code}"
    )
