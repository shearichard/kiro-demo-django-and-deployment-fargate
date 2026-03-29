# Implementation Plan: Django Survey App

## Overview

Implement a Django + PostgreSQL survey application with token-based participant access, admin management via Django admin, aggregated results view, and Docker-based containerisation. Tasks follow an incremental approach: models → admin → views/forms → templates → containerisation → tests.

## Tasks

- [x] 1. Project scaffold and configuration
  - Create the Django project (`django_survey`) and `survey` app using `django-admin startproject` / `manage.py startapp`
  - Add `requirements.txt` with `django`, `psycopg2-binary`, `gunicorn`, `whitenoise`, `dj-database-url`, `django-environ`, `hypothesis`, `pytest`, `pytest-django`
  - Configure `django_survey/settings.py` to read `SECRET_KEY`, `DATABASE_URL`, `DEBUG`, and `ALLOWED_HOSTS` from environment variables via `django-environ`
  - Add `whitenoise.middleware.WhiteNoiseMiddleware` to `MIDDLEWARE` and configure `STATIC_ROOT`
  - Create `pytest.ini` with `DJANGO_SETTINGS_MODULE = django_survey.settings` and `conftest.py` with pytest-django setup
  - _Requirements: 6.3, 6.5, 7.1, 7.4_

- [x] 2. Data models
  - [x] 2.1 Implement `Survey`, `Question`, `AccessToken`, and `Response` models in `survey/models.py` exactly as specified in the design
    - Include `unique=True` on `Survey.name`, `CASCADE` deletes on all FK fields, `MinValueValidator`/`MaxValueValidator` on `Response.value`, and `unique_together` on `(question, access_token)`
    - Add `generate_token()` helper using `secrets.token_urlsafe(32)`
    - Create and run initial migration
    - _Requirements: 1.1, 1.5, 2.2, 2.3, 2.5, 3.2, 3.3_

  - [x] 2.2 Write property test for Survey name uniqueness (Property 1)
    - **Property 1: Survey name uniqueness**
    - **Validates: Requirements 1.1**

  - [x] 2.3 Write property test for Survey update round-trip (Property 2)
    - **Property 2: Survey update round-trip**
    - **Validates: Requirements 1.2**

  - [x] 2.4 Write property test for Survey cascade delete (Property 3)
    - **Property 3: Survey cascade delete**
    - **Validates: Requirements 1.5**

  - [x] 2.5 Write property test for Question blank text rejection (Property 4)
    - **Property 4: Question blank text rejection**
    - **Validates: Requirements 2.2**

  - [x] 2.6 Write property test for Response value range enforcement (Property 5)
    - **Property 5: Response value range enforcement**
    - **Validates: Requirements 2.3, 4.7, 4.8**

  - [x]* 2.7 Write property test for Question cascade delete (Property 6)
    - **Property 6: Question cascade delete**
    - **Validates: Requirements 2.5**

  - [x]* 2.8 Write property test for token length, URL-safety, and uniqueness (Property 7)
    - **Property 7: Token length, URL-safety, and uniqueness**
    - **Validates: Requirements 3.2, 3.3, 3.5**

- [x] 3. Checkpoint — Ensure all model-level tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Django admin registrations
  - [x] 4.1 Implement `survey/admin.py` with `SurveyAdmin` (inline `QuestionInline`), `AccessTokenAdmin`, and the `generate_tokens` bulk-create action
    - `SurveyAdmin`: list display with name, question count, token count; `QuestionInline` for adding/removing questions inline
    - `AccessTokenAdmin`: list display with survey, token preview, used status, created date; `generate_tokens` action that accepts a count and calls `AccessToken.objects.bulk_create`
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.4, 3.1, 3.5_

  - [x] 4.2 Write unit test for `generate_tokens` admin action
    - Assert the action creates the requested number of tokens associated with the correct survey
    - _Requirements: 3.1, 3.5_

- [x] 5. Participant views and form
  - [x] 5.1 Implement `SurveyResponseForm` in `survey/forms.py`
    - Dynamically build one `ChoiceField` (radio, choices 1–5) per question from the survey's question set
    - _Requirements: 2.3, 4.4, 4.7, 4.8_

  - [x] 5.2 Implement `SurveyView` (GET + POST) in `survey/views.py`
    - GET: look up `AccessToken` by token string (404 if missing), render `already_used.html` if `used=True`, otherwise render survey form
    - POST: validate form, save `Response` objects, mark token used, redirect to confirmation URL
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 5.3 Implement `ConfirmationView` in `survey/views.py`
    - Renders `confirmation.html` for the given token
    - _Requirements: 4.6_

  - [x] 5.4 Wire URL patterns in `survey/urls.py` and include them in `django_survey/urls.py`
    - `/survey/<str:token>/` → `SurveyView`
    - `/survey/<str:token>/done/` → `ConfirmationView`
    - `/survey/<str:token>/results/` → `ResultsView`
    - _Requirements: 3.4_

  - [x] 5.5 Write property test for valid unused token GET (Property 8)
    - **Property 8: Valid unused token displays survey and all questions**
    - **Validates: Requirements 4.1**

  - [x] 5.6 Write property test for used token GET (Property 9)
    - **Property 9: Used token shows already-completed message**
    - **Validates: Requirements 4.2**

  - [x] 5.7 Write property test for non-existent token 404 (Property 10)
    - **Property 10: Non-existent token returns 404**
    - **Validates: Requirements 4.3**

  - [x] 5.8 Write property test for valid partial submission (Property 11)
    - **Property 11: Valid partial submission records responses and marks token used**
    - **Validates: Requirements 4.4, 4.5, 4.6**

  - [x] 5.9 Write property test for out-of-range submission rejection (Property 12)
    - **Property 12: Out-of-range submission is rejected**
    - **Validates: Requirements 4.8**

- [x] 6. Results view
  - [x] 6.1 Implement `ResultsView` in `survey/views.py`
    - Decorate with `@login_required`
    - Aggregate `Response` counts using `values('question_id', 'value').annotate(count=Count('id'))` and build the `{question_id: {value: count}}` mapping from the design
    - Pass questions, result map, and total submission count to `results.html`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 6.2 Write unit test for results view authentication
    - Assert unauthenticated request returns redirect/403
    - Assert authenticated staff request returns HTTP 200
    - _Requirements: 5.1_

  - [x] 6.3 Write property test for results counts accuracy (Property 13)
    - **Property 13: Results counts accuracy**
    - **Validates: Requirements 5.2, 5.3, 5.4**

- [x] 7. Checkpoint — Ensure all view and results tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Templates and responsive UI
  - [x] 8.1 Create `survey/templates/survey/base.html` with Bootstrap 5 CDN link and responsive viewport meta tag
    - _Requirements: 8.1_

  - [x] 8.2 Create `survey_form.html` extending `base.html`
    - Render each question as a `<fieldset>` with five `form-check-inline` radio buttons (values 1–5)
    - Use Bootstrap grid (`col-12 col-md-*`) so the layout reflows at 320px without horizontal scrolling
    - _Requirements: 4.1, 8.2, 8.4_

  - [x] 8.3 Create `already_used.html` extending `base.html`
    - Display a clear message that the survey has already been completed; no form element
    - _Requirements: 4.2_

  - [x] 8.4 Create `confirmation.html` extending `base.html`
    - Display a submission-received confirmation message
    - _Requirements: 4.6_

  - [x] 8.5 Create `results.html` extending `base.html`
    - Render a table of question × value counts wrapped in a `table-responsive` div
    - Display total submission count
    - _Requirements: 5.2, 5.3, 5.5, 8.3, 8.5_

  - [ ]* 8.6 Write unit tests for template content
    - Assert `base.html` (or rendered survey page) contains Bootstrap 5 CDN `<link>`
    - Assert `results.html` wraps the table in a `table-responsive` div
    - _Requirements: 8.1, 8.5_

- [x] 9. Containerisation
  - [x] 9.1 Create `Dockerfile` as specified in the design
    - `FROM python:3.12-slim`, install dependencies, copy source, run `collectstatic`, expose 8000, set `ENTRYPOINT`
    - _Requirements: 6.4, 7.3_

  - [x] 9.2 Create `entrypoint.sh` that runs `migrate --noinput` then starts gunicorn
    - _Requirements: 7.2_

  - [x] 9.3 Create `docker-compose.yml` with `db` (postgres:16) and `web` services as specified in the design
    - Map port 8000, pass all required environment variables, set `depends_on: db`
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 9.4 Verify migrations run cleanly against Postgres on first `docker compose up`
    - Note: migrations during Tasks 2–8 run against SQLite (no Postgres available locally). Once the Docker Compose stack is up, confirm `entrypoint.sh` applies all migrations successfully against the Postgres container on first startup.
    - _Requirements: 7.2_

  - [ ]* 9.5 Write unit tests for containerisation artefacts
    - Assert `docker-compose.yml` and `Dockerfile` exist at the repository root
    - Assert `settings.py` reads `DATABASE_URL` from environment
    - Assert `DEBUG=False` in environment results in `settings.DEBUG == False`
    - _Requirements: 6.1, 6.4, 6.5, 7.1, 7.4_

- [x] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `@settings(max_examples=100)` minimum; increase to 200 for critical properties (P5, P11, P12, P13)
- Each property test must include a comment: `# Feature: django-survey-app, Property N: <title>`
- Run tests with: `pytest --tb=short -q`
