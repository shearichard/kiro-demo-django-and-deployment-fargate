"""
Unit tests for results view authentication.
Validates: Requirements 5.1
"""
import pytest
from django.contrib.auth.models import User

from survey.models import AccessToken, Survey


@pytest.fixture
def survey_with_token(db):
    survey = Survey.objects.create(name="Results Auth Test Survey")
    token = AccessToken.objects.create(survey=survey)
    return survey, token


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff", password="pass", is_staff=True
    )


@pytest.mark.django_db
def test_unauthenticated_results_request_redirects(client, survey_with_token):
    """Unauthenticated request to results view should redirect to login. (Req 5.1)"""
    _, token = survey_with_token
    response = client.get(f"/survey/{token.token}/results/")
    assert response.status_code in (302, 403)
    if response.status_code == 302:
        assert "/login" in response["Location"] or "login" in response["Location"].lower()


@pytest.mark.django_db
def test_authenticated_staff_results_request_returns_200(client, survey_with_token, staff_user):
    """Authenticated staff request to results view should return HTTP 200. (Req 5.1)"""
    _, token = survey_with_token
    client.force_login(staff_user)
    response = client.get(f"/survey/{token.token}/results/")
    assert response.status_code == 200
