"""
Unit tests for survey admin actions.
Validates: Requirements 3.1, 3.5
"""
import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from survey.admin import AccessTokenAdmin, generate_tokens
from survey.models import AccessToken, Survey


@pytest.fixture
def survey(db):
    return Survey.objects.create(name="Admin Test Survey")


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="admin", password="pass", email="a@b.com")


def make_request(rf, admin_user, count):
    """Build a POST request with messages middleware support."""
    request = rf.post("/", data={"token_count": str(count)})
    request.user = admin_user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


@pytest.mark.django_db
def test_generate_tokens_creates_correct_count(survey, admin_user):
    """generate_tokens creates exactly the requested number of tokens. (Req 3.1, 3.5)"""
    count = 7
    request = make_request(RequestFactory(), admin_user, count)

    site = AdminSite()
    ma = AccessTokenAdmin(AccessToken, site)
    generate_tokens(ma, request, Survey.objects.filter(pk=survey.pk))

    assert AccessToken.objects.filter(survey=survey).count() == count


@pytest.mark.django_db
def test_generate_tokens_associates_correct_survey(survey, admin_user):
    """All tokens created by generate_tokens belong to the selected survey. (Req 3.1)"""
    other_survey = Survey.objects.create(name="Other Survey")
    count = 5
    request = make_request(RequestFactory(), admin_user, count)

    site = AdminSite()
    ma = AccessTokenAdmin(AccessToken, site)
    generate_tokens(ma, request, Survey.objects.filter(pk=survey.pk))

    assert AccessToken.objects.filter(survey=survey).count() == count
    assert AccessToken.objects.filter(survey=other_survey).count() == 0


@pytest.mark.django_db
def test_generate_tokens_multiple_surveys(admin_user):
    """generate_tokens creates tokens for each survey in the queryset. (Req 3.5)"""
    s1 = Survey.objects.create(name="Survey One")
    s2 = Survey.objects.create(name="Survey Two")
    count = 3
    request = make_request(RequestFactory(), admin_user, count)

    site = AdminSite()
    ma = AccessTokenAdmin(AccessToken, site)
    generate_tokens(ma, request, Survey.objects.filter(pk__in=[s1.pk, s2.pk]))

    assert AccessToken.objects.filter(survey=s1).count() == count
    assert AccessToken.objects.filter(survey=s2).count() == count
