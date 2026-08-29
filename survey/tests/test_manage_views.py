"""
Unit tests for survey management views.
Covers: survey_list_view, survey_create_view, survey_detail_view,
        question_add_view, token_create_view.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from survey.models import AccessToken, Question, Survey


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, password="pass1234"):
    return User.objects.create_user(username=username, password=password)


def make_survey(owner, name="My Survey", description=""):
    return Survey.objects.create(owner=owner, name=name, description=description)


def make_question(survey, text="Rate this"):
    return Question.objects.create(survey=survey, text=text)


def make_token(survey, used=False):
    token = AccessToken.objects.create(survey=survey)
    if used:
        token.used = True
        token.save()
    return token


# ---------------------------------------------------------------------------
# survey_list_view  (Requirements 4.1–4.5)
# ---------------------------------------------------------------------------

class SurveyListViewTests(TestCase):

    def setUp(self):
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.client = Client()
        self.url = reverse("manage:survey_list")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/accounts/login/?next={self.url}", fetch_redirect_response=False)

    def test_authenticated_owner_sees_own_surveys(self):
        s = make_survey(self.owner, name="Owned Survey")
        make_survey(self.other, name="Other Survey")
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        surveys = list(response.context["surveys"])
        self.assertEqual(len(surveys), 1)
        self.assertEqual(surveys[0].pk, s.pk)

    def test_other_users_surveys_are_hidden(self):
        make_survey(self.other, name="Invisible Survey")
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(len(list(response.context["surveys"])), 0)

    def test_empty_state_renders_for_user_with_no_surveys(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list(response.context["surveys"])), 0)

    def test_token_count_annotation(self):
        s = make_survey(self.owner)
        make_token(s)
        make_token(s)
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        survey = list(response.context["surveys"])[0]
        self.assertEqual(survey.token_count, 2)

    def test_used_token_count_annotation(self):
        s = make_survey(self.owner)
        make_token(s, used=True)
        make_token(s, used=False)
        make_token(s, used=True)
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        survey = list(response.context["surveys"])[0]
        self.assertEqual(survey.used_token_count, 2)
        self.assertEqual(survey.token_count, 3)

    def test_token_counts_are_zero_for_new_survey(self):
        make_survey(self.owner)
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        survey = list(response.context["surveys"])[0]
        self.assertEqual(survey.token_count, 0)
        self.assertEqual(survey.used_token_count, 0)


# ---------------------------------------------------------------------------
# survey_create_view  (Requirements 2.1–2.5)
# ---------------------------------------------------------------------------

class SurveyCreateViewTests(TestCase):

    def setUp(self):
        self.owner = make_user("creator")
        self.client = Client()
        self.url = reverse("manage:survey_create")

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/accounts/login/?next={self.url}", fetch_redirect_response=False)

    def test_unauthenticated_post_redirects_to_login(self):
        response = self.client.post(self.url, {"name": "Survey", "description": ""})
        self.assertRedirects(response, f"/accounts/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_renders_empty_form(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_valid_post_creates_survey_with_owner(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, {"name": "New Survey", "description": "Desc"})
        survey = Survey.objects.get(name="New Survey")
        self.assertEqual(survey.owner, self.owner)

    def test_valid_post_redirects_to_detail(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {"name": "Redirect Survey", "description": ""})
        survey = Survey.objects.get(name="Redirect Survey")
        self.assertRedirects(response, reverse("manage:survey_detail", kwargs={"pk": survey.pk}), fetch_redirect_response=False)

    def test_blank_name_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {"name": "", "description": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Survey.objects.filter(name="").exists())
        self.assertTrue(response.context["form"].errors)

    def test_whitespace_only_name_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {"name": "   ", "description": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Survey.objects.count(), 0)
        self.assertIn("name", response.context["form"].errors)

    def test_duplicate_name_rejected(self):
        make_survey(self.owner, name="Taken Name")
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {"name": "Taken Name", "description": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Survey.objects.filter(name="Taken Name").count(), 1)
        self.assertIn("name", response.context["form"].errors)


# ---------------------------------------------------------------------------
# survey_detail_view  (Requirements 6.1–6.4)
# ---------------------------------------------------------------------------

class SurveyDetailViewTests(TestCase):

    def setUp(self):
        self.owner = make_user("detail_owner")
        self.other = make_user("detail_other")
        self.survey = make_survey(self.owner, name="Detail Survey")
        self.url = reverse("manage:survey_detail", kwargs={"pk": self.survey.pk})
        self.client = Client()

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/accounts/login/?next={self.url}", fetch_redirect_response=False)

    def test_non_owner_gets_403(self):
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_unknown_pk_returns_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("manage:survey_detail", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)

    def test_owner_sees_survey_name_and_description(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["survey"], self.survey)

    def test_owner_sees_questions(self):
        q1 = make_question(self.survey, text="Q1")
        q2 = make_question(self.survey, text="Q2")
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        questions = list(response.context["questions"])
        self.assertIn(q1, questions)
        self.assertIn(q2, questions)

    def test_detail_page_contains_token_create_form(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        token_create_url = reverse("manage:token_create", kwargs={"pk": self.survey.pk})
        self.assertContains(response, token_create_url)


# ---------------------------------------------------------------------------
# question_add_view  (Requirements 3.1–3.5)
# ---------------------------------------------------------------------------

class QuestionAddViewTests(TestCase):

    def setUp(self):
        self.owner = make_user("q_owner")
        self.other = make_user("q_other")
        self.survey = make_survey(self.owner, name="Q Survey")
        self.url = reverse("manage:question_add", kwargs={"pk": self.survey.pk})
        self.client = Client()

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/accounts/login/?next={self.url}", fetch_redirect_response=False)

    def test_non_owner_get_returns_403(self):
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_non_owner_post_returns_403_and_no_question_created(self):
        self.client.force_login(self.other)
        response = self.client.post(self.url, {"text": "Sneaky question"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Question.objects.filter(survey=self.survey).count(), 0)

    def test_owner_get_renders_form(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_owner_valid_post_creates_question(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, {"text": "Valid question?", "order": 0})
        self.assertEqual(Question.objects.filter(survey=self.survey, text="Valid question?").count(), 1)

    def test_owner_valid_post_redirects_to_detail(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {"text": "Redirect question?", "order": 0})
        self.assertRedirects(response, reverse("manage:survey_detail", kwargs={"pk": self.survey.pk}), fetch_redirect_response=False)

    def test_blank_text_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {"text": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.filter(survey=self.survey).count(), 0)
        self.assertIn("text", response.context["form"].errors)

    def test_whitespace_only_text_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {"text": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.filter(survey=self.survey).count(), 0)
        self.assertTrue(response.context["form"].errors)

    def test_unknown_survey_pk_returns_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("manage:question_add", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# token_create_view  (Requirements 5.1–5.4)
# ---------------------------------------------------------------------------

class TokenCreateViewTests(TestCase):

    def setUp(self):
        self.owner = make_user("tok_owner")
        self.other = make_user("tok_other")
        self.survey = make_survey(self.owner, name="Token Survey")
        self.url = reverse("manage:token_create", kwargs={"pk": self.survey.pk})
        self.client = Client()

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, f"/accounts/login/?next={self.url}", fetch_redirect_response=False)

    def test_non_owner_post_returns_403(self):
        self.client.force_login(self.other)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_non_owner_post_creates_no_token(self):
        self.client.force_login(self.other)
        self.client.post(self.url)
        self.assertEqual(AccessToken.objects.filter(survey=self.survey).count(), 0)

    def test_owner_post_creates_token(self):
        self.client.force_login(self.owner)
        self.client.post(self.url)
        self.assertEqual(AccessToken.objects.filter(survey=self.survey).count(), 1)

    def test_owner_post_shows_token_value_in_response(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        token = AccessToken.objects.get(survey=self.survey)
        self.assertContains(response, token.token)

    def test_owner_get_redirects_to_detail(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("manage:survey_detail", kwargs={"pk": self.survey.pk}), fetch_redirect_response=False)

    def test_unknown_survey_pk_returns_404(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("manage:token_create", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)
