# Implementation Plan: Survey User Management

## Overview

Extend the Django survey app with an authenticated management UI. Adds an `owner` FK to `Survey`, new management views/URLs, forms, templates, and a comprehensive test suite.

## Tasks

- [x] 1. Add `owner` FK to `Survey` model with migrations
  - [x] 1.1 Add `owner` nullable FK to `Survey` in `survey/models.py`
    - Add `owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='surveys', null=True)` to `Survey`
    - Add `from django.conf import settings` import
    - Generate migration: `python manage.py makemigrations survey`
    - _Requirements: 1.1, 1.3_

  - [x] 1.2 Create data migration to assign existing surveys to first superuser
    - Generate empty data migration: `python manage.py makemigrations survey --empty --name assign_survey_owners`
    - Write `RunPython` operation that sets `owner` to the first superuser if one exists, otherwise leaves NULL
    - _Requirements: 1.1_

  - [x] 1.3 Make `owner` non-nullable with a third migration
    - Change `null=True` to `null=False` on `Survey.owner` in `models.py`
    - Generate migration: `python manage.py makemigrations survey`
    - _Requirements: 1.1_

  - [ ]* 1.4 Write property test for owner cascade delete (Property 2)
    - Add `test_manage_properties.py` in `survey/tests/` with `@given` test
    - **Property 2: Owner cascade delete removes surveys**
    - **Validates: Requirements 1.3**
    - Tag: `# Feature: survey-user-management, Property 2: Owner cascade delete removes surveys`

- [x] 2. Add `SurveyForm` and `QuestionForm` to `survey/forms.py`
  - [x] 2.1 Implement `SurveyForm` ModelForm
    - Add `SurveyForm(forms.ModelForm)` for `Survey` with fields `name`, `description`
    - Apply `validate_not_blank` as a validator on the `name` field via `clean_name()`
    - _Requirements: 2.3, 2.4_

  - [x] 2.2 Implement `QuestionForm` ModelForm
    - Add `QuestionForm(forms.ModelForm)` for `Question` with field `text`
    - Model-level `validate_not_blank` on `Question.text` already handles blank rejection
    - _Requirements: 3.3_

  - [ ]* 2.3 Write unit tests for `SurveyForm` in `survey/tests/test_manage_forms.py`
    - Test valid submission, blank name, whitespace-only name, duplicate name
    - _Requirements: 2.3, 2.4_

  - [ ]* 2.4 Write unit tests for `QuestionForm`
    - Test valid text, blank text, whitespace-only text
    - _Requirements: 3.3_

  - [ ]* 2.5 Write property test for whitespace survey name rejection (Property 3)
    - **Property 3: Whitespace-only name is rejected**
    - **Validates: Requirements 2.3**
    - Tag: `# Feature: survey-user-management, Property 3: Whitespace-only name is rejected`

  - [ ]* 2.6 Write property test for duplicate survey name rejection (Property 4)
    - **Property 4: Duplicate survey name is rejected**
    - **Validates: Requirements 2.4**

  - [ ]* 2.7 Write property test for whitespace question text rejection (Property 5)
    - **Property 5: Whitespace-only question text is rejected**
    - **Validates: Requirements 3.3**

- [ ] 3. Checkpoint — Ensure all tests pass
  - Run `.venv/bin/pytest survey/tests/test_manage_forms.py` and ensure all pass; ask the user if questions arise.

- [-] 4. Create `survey/manage_views.py` with all five management views
  - [ ] 4.1 Implement `survey_list_view`
    - Filter surveys by `owner=request.user`; annotate each with `token_count` and `used_token_count` via `Count` and conditional aggregation
    - Render `survey/manage/survey_list.html`
    - _Requirements: 4.1, 4.3, 4.4, 4.5_

  - [ ] 4.2 Implement `survey_create_view`
    - On GET render empty `SurveyForm`; on valid POST set `survey.owner = request.user`, save, redirect to `manage:survey_detail`
    - _Requirements: 2.1, 2.2, 2.5_

  - [ ] 4.3 Implement `survey_detail_view`
    - `get_object_or_404(Survey, pk=pk)`; return 403 if `survey.owner != request.user`
    - Pass survey and its questions to `survey/manage/survey_detail.html`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ] 4.4 Implement `question_add_view`
    - Ownership check → 403; on valid POST create `Question` linked to survey, redirect to `manage:survey_detail`
    - _Requirements: 3.1, 3.2, 3.4, 3.5_

  - [ ] 4.5 Implement `token_create_view`
    - Ownership check → 403; on POST create `AccessToken` (default `generate_token()` fires automatically)
    - Render `survey/manage/token_created.html` with the new token value
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [-] 5. Create `survey/manage_urls.py` and wire into `django_survey/urls.py`
  - [x] 5.1 Create `survey/manage_urls.py` with all five URL patterns and `app_name = 'manage'`
    - Patterns: `surveys/`, `surveys/new/`, `surveys/<int:pk>/`, `surveys/<int:pk>/questions/add/`, `surveys/<int:pk>/tokens/create/`
    - _Requirements: 2.2, 3.2, 4.2, 5.2, 6.2_

  - [x] 5.2 Include `manage_urls.py` in `django_survey/urls.py` under `/survey/manage/`
    - Add `path('survey/manage/', include('survey.manage_urls'))` before the existing `survey/` include
    - _Requirements: all management URL requirements_

- [ ] 6. Create management templates
  - [x] 6.1 Create `survey/templates/survey/manage/survey_list.html`
    - Extend `base.html`; show table of owned surveys with name, token_count, used_token_count; empty-state message when list is empty; link to create page
    - _Requirements: 4.1, 4.3, 4.4, 4.5_

  - [x] 6.2 Create `survey/templates/survey/manage/survey_create.html`
    - Extend `base.html`; render `SurveyForm` with Bootstrap 5 form classes and CSRF token
    - _Requirements: 2.1, 2.3_

  - [x] 6.3 Create `survey/templates/survey/manage/survey_detail.html`
    - Extend `base.html`; display survey name, description, ordered question list, and a POST button/form to issue a new token
    - _Requirements: 6.1, 6.4_

  - [x] 6.4 Create `survey/templates/survey/manage/question_add.html`
    - Extend `base.html`; render `QuestionForm` with Bootstrap 5 classes and CSRF token
    - _Requirements: 3.1, 3.3_

  - [x] 6.5 Create `survey/templates/survey/manage/token_created.html`
    - Extend `base.html`; display the full token value prominently and a link back to the survey detail page
    - _Requirements: 5.4_

- [x] 7. Write unit tests for management views in `survey/tests/test_manage_views.py`
  - [x] 7.1 Write unit tests for `survey_list_view`
    - Authenticated owner sees own surveys; unauthenticated user is redirected; other user's surveys are hidden; token counts are correct; empty-state renders
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 7.2 Write unit tests for `survey_create_view`
    - Valid POST creates survey and redirects; unauthenticated redirects to login; blank name rejected; duplicate name rejected
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 7.3 Write unit tests for `survey_detail_view`
    - Owner sees questions and token-issue control; unauthenticated redirects; non-owner gets 403; 404 on unknown pk
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 7.4 Write unit tests for `question_add_view`
    - Owner POST adds question and redirects; unauthenticated redirects; non-owner gets 403; blank text rejected
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 7.5 Write unit tests for `token_create_view`
    - Owner POST creates token and displays value; unauthenticated redirects; non-owner gets 403; token value shown in response
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 8. Checkpoint — Ensure all tests pass
  - Run `.venv/bin/pytest survey/tests/test_manage_views.py survey/tests/test_manage_forms.py` and ensure all pass; ask the user if questions arise.

- [ ] 9. Write property-based tests in `survey/tests/test_manage_properties.py`
  - [ ]* 9.1 Write property test for survey creation sets owner (Property 1)
    - **Property 1: Survey creation sets owner to current user**
    - **Validates: Requirements 1.2, 2.1**
    - Tag: `# Feature: survey-user-management, Property 1: Survey creation sets owner to current user`

  - [ ]* 9.2 Write property test for owner cascade delete (Property 2)
    - **Property 2: Owner cascade delete removes surveys**
    - **Validates: Requirements 1.3**
    - (Move here if not already written in task 1.4)

  - [ ]* 9.3 Write property test for whitespace survey name rejection (Property 3)
    - **Property 3: Whitespace-only name is rejected**
    - **Validates: Requirements 2.3**
    - (Move here if not already written in task 2.5)

  - [ ]* 9.4 Write property test for duplicate survey name rejection (Property 4)
    - **Property 4: Duplicate survey name is rejected**
    - **Validates: Requirements 2.4**

  - [ ]* 9.5 Write property test for whitespace question text rejection (Property 5)
    - **Property 5: Whitespace-only question text is rejected**
    - **Validates: Requirements 3.3**

  - [ ]* 9.6 Write property test for non-owner add-question returns 403 (Property 6)
    - **Property 6: Non-owner cannot add question (403)**
    - **Validates: Requirements 3.4**

  - [ ]* 9.7 Write property test for survey list scoped to current user (Property 7)
    - **Property 7: Survey list is scoped to current user**
    - **Validates: Requirements 4.1**
    - Use `st.integers(min_value=1, max_value=10)` for survey counts per user

  - [ ]* 9.8 Write property test for token statistics accuracy (Property 8)
    - **Property 8: Token statistics are accurate per survey**
    - **Validates: Requirements 4.3, 4.4**
    - Use `st.integers(min_value=0, max_value=50)` for token counts

  - [ ]* 9.9 Write property test for non-owner token create returns 403 (Property 9)
    - **Property 9: Non-owner cannot create token (403)**
    - **Validates: Requirements 5.3**

  - [ ]* 9.10 Write property test for generated token URL-safety and length (Property 10)
    - **Property 10: Generated tokens are URL-safe and at least 32 characters**
    - **Validates: Requirements 5.5**
    - Note: `generate_token()` already tested in `test_model_properties.py`; verify or consolidate

  - [ ]* 9.11 Write property test for non-owner detail view returns 403 (Property 11)
    - **Property 11: Non-owner cannot view survey detail (403)**
    - **Validates: Requirements 6.3**

- [ ] 10. Final checkpoint — Ensure all tests pass
  - Run `.venv/bin/pytest survey/tests/` and ensure all pass; ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Properties 3, 4, 5 and 10 overlap with existing model-level tests in `test_model_properties.py` — the property tests here validate them via the view/form layer
- The two-step migration (nullable → data migration → non-nullable) is the safe path; in a fresh dev environment a single nullable migration is also acceptable
- All management views use `@login_required` and `HttpResponseForbidden` for ownership gating — no middleware changes needed
- Bootstrap 5 templates must extend `base.html` and follow the same pattern as existing participant templates
