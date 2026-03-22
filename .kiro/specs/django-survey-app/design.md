# Design Document: Django Survey App

## Overview

A Django + PostgreSQL web application for creating and distributing 1–5 scale surveys. Administrators manage surveys, questions, and access tokens through the Django admin interface. Participants receive unique single-use URLs and submit responses through a simple participant-facing UI. Aggregated results are available to admins. The application is containerised with Docker Compose for local development and a Dockerfile for AWS Fargate deployment.

### Key Design Decisions

- **Django admin for all admin operations**: Avoids building a custom admin UI; leverages Django's built-in CRUD, authentication, and permissions.
- **Token-based access (no login for participants)**: Participants access surveys via a cryptographically random URL token — no account creation required.
- **Single Django app (`survey`)**: The feature set is cohesive enough to live in one app; avoids premature splitting.
- **WhiteNoise for static files**: Serves `collectstatic` output directly from the Django process — appropriate for Fargate where a separate static file server adds complexity.
- **Bootstrap 5 via CDN in base template**: Keeps the Docker image lean; no Node.js build step required.

---

## Architecture

```mermaid
graph TD
    subgraph Docker Compose (local)
        A[Django app container :8000] -->|psycopg2| B[(PostgreSQL container :5432)]
    end

    subgraph AWS Fargate (production)
        C[Django app container] -->|psycopg2| D[(Amazon RDS PostgreSQL)]
        E[ALB / CloudFront] --> C
    end

    Admin -->|/admin/| A
    Admin -->|/admin/| C
    Participant -->|/survey/<token>/| A
    Participant -->|/survey/<token>/| C
```

### Request Flow

```mermaid
sequenceDiagram
    participant P as Participant
    participant D as Django
    participant DB as PostgreSQL

    P->>D: GET /survey/<token>/
    D->>DB: SELECT AccessToken WHERE token=<token>
    DB-->>D: token row (used=False)
    D-->>P: Render survey form

    P->>D: POST /survey/<token>/
    D->>DB: Validate token (used=False)
    D->>DB: INSERT Response rows
    D->>DB: UPDATE AccessToken SET used=True
    DB-->>D: OK
    D-->>P: Render confirmation page
```

---

## Components and Interfaces

### Django Project Layout

```
django_survey/          # project package (settings, urls, wsgi)
survey/                 # single Django app
  models.py             # Survey, Question, AccessToken, Response
  admin.py              # ModelAdmin registrations + token generation action
  views.py              # SurveyView (GET/POST), ConfirmationView, ResultsView
  forms.py              # SurveyResponseForm (dynamic, per-token)
  urls.py               # URL patterns
  templates/
    survey/
      base.html         # Bootstrap 5 base template
      survey_form.html  # Participant survey page
      already_used.html # Already-submitted message
      confirmation.html # Post-submission confirmation
      results.html      # Admin results view
requirements.txt
Dockerfile
docker-compose.yml
entrypoint.sh           # migrate + collectstatic + gunicorn
```

### URL Patterns

| Pattern | View | Purpose |
|---|---|---|
| `/survey/<str:token>/` | `SurveyView` | Participant survey (GET + POST) |
| `/survey/<str:token>/done/` | `ConfirmationView` | Post-submission confirmation |
| `/survey/<str:token>/results/` | `ResultsView` | Admin results page (login required) |
| `/admin/` | Django admin | Admin CRUD + token generation |

### Admin Interface

- `SurveyAdmin`: list display (name, question count, token count), inline `QuestionInline`.
- `AccessTokenAdmin`: list display (survey, token preview, used status, created date), custom action `generate_tokens` that prompts for a count and bulk-creates tokens.
- `ResultsView` linked from `AccessTokenAdmin` change list via a custom button.

### Views

**`SurveyView`** (`GET /survey/<token>/`)
- Looks up `AccessToken` by token string; 404 if not found.
- If `used=True`, renders `already_used.html`.
- Builds `SurveyResponseForm` dynamically from the survey's questions.
- `POST`: validates form, saves `Response` objects, marks token used, redirects to confirmation.

**`ResultsView`** (`GET /survey/<token>/results/`)
- Decorated with `@login_required`.
- Aggregates `Response` counts using `values('question', 'value').annotate(count=Count('id'))`.
- Passes structured data to `results.html`.

---

## Data Models

```mermaid
erDiagram
    Survey ||--o{ Question : "has"
    Survey ||--o{ AccessToken : "has"
    Question ||--o{ Response : "has"
    AccessToken ||--o{ Response : "has"

    Survey {
        int id PK
        varchar name UK
        text description
        datetime created_at
    }

    Question {
        int id PK
        int survey_id FK
        text text
        int order
    }

    AccessToken {
        int id PK
        int survey_id FK
        varchar token UK
        bool used
        datetime created_at
    }

    Response {
        int id PK
        int question_id FK
        int access_token_id FK
        int value
        datetime created_at
    }
```

### Model Details

**`Survey`**
```python
class Survey(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```
- Cascade delete propagates to `Question` and `AccessToken` (and transitively to `Response`).

**`Question`**
```python
class Question(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
```
- `text` is non-nullable and non-blank (enforced at model + form level).
- Cascade delete propagates to `Response`.

**`AccessToken`**
```python
class AccessToken(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='tokens')
    token = models.CharField(max_length=64, unique=True)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```
- Token generated via `secrets.token_urlsafe(32)` (produces 43 URL-safe characters, ≥32 chars, cryptographically random).

**`Response`**
```python
SCALE_CHOICES = [(i, str(i)) for i in range(1, 6)]

class Response(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='responses')
    access_token = models.ForeignKey(AccessToken, on_delete=models.CASCADE, related_name='responses')
    value = models.IntegerField(choices=SCALE_CHOICES,
                                validators=[MinValueValidator(1), MaxValueValidator(5)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('question', 'access_token')]
```
- `unique_together` prevents duplicate responses per question per token.
- `MinValueValidator`/`MaxValueValidator` enforce the 1–5 constraint at the ORM level.

### Token Generation

```python
import secrets

def generate_token():
    return secrets.token_urlsafe(32)  # 43 chars, URL-safe base64
```

Called in the admin action; tokens are bulk-created in a single `bulk_create` call.

### Results Aggregation Query

```python
from django.db.models import Count

def get_results(survey):
    questions = survey.questions.prefetch_related('responses').all()
    counts = (
        Response.objects
        .filter(question__survey=survey)
        .values('question_id', 'value')
        .annotate(count=Count('id'))
    )
    # Build {question_id: {value: count}} mapping
    result_map = {}
    for row in counts:
        result_map.setdefault(row['question_id'], {})[row['value']] = row['count']
    return questions, result_map
```

### Cascade Delete Behaviour

| Deleted entity | Also deleted |
|---|---|
| `Survey` | All `Question`, `AccessToken`, `Response` for that survey |
| `Question` | All `Response` for that question |
| `AccessToken` | All `Response` for that token |

All cascades are handled by Django's `on_delete=models.CASCADE` — no custom signals needed.

---

## Containerisation

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
```

### entrypoint.sh

```bash
#!/bin/sh
set -e
python manage.py migrate --noinput
exec gunicorn django_survey.wsgi:application \
     --bind 0.0.0.0:8000 \
     --workers 2
```

### docker-compose.yml (local dev)

```yaml
version: "3.9"
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: survey
      POSTGRES_USER: survey
      POSTGRES_PASSWORD: survey
    ports:
      - "5432:5432"

  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgres://survey:survey@db:5432/survey
      SECRET_KEY: dev-secret-key
      DEBUG: "True"
      ALLOWED_HOSTS: "localhost,127.0.0.1"
    depends_on:
      - db
```

### Environment Variables

| Variable | Purpose | Example |
|---|---|---|
| `SECRET_KEY` | Django secret key | `<random 50-char string>` |
| `DATABASE_URL` | Full DB connection string | `postgres://user:pass@host:5432/db` |
| `DEBUG` | Django debug mode | `True` / `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `myapp.example.com` |

`django-environ` or `dj-database-url` parses `DATABASE_URL` into Django's `DATABASES` dict.

---

## Responsive UI

All participant-facing and results pages extend `base.html` which loads Bootstrap 5 via CDN. Layout uses Bootstrap's grid (`col-12 col-md-*`) so pages reflow correctly at 320px.

- Survey form: each question is a `<fieldset>` with five radio buttons rendered as `form-check-inline` items. On narrow screens they wrap naturally.
- Results table: wrapped in `table-responsive` div so the table scrolls horizontally within its container rather than the whole page, keeping question text readable.
- No custom CSS breakpoints needed beyond Bootstrap defaults.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Survey name uniqueness

*For any* two surveys, if they have the same name, the second creation attempt should be rejected with an integrity error; surveys with distinct names should all be created successfully.

**Validates: Requirements 1.1**

---

### Property 2: Survey update round-trip

*For any* existing survey and any new valid name/description pair, updating the survey and then reading it back should return exactly the values that were written.

**Validates: Requirements 1.2**

---

### Property 3: Survey cascade delete

*For any* survey that has associated questions, access tokens, and responses, deleting the survey should result in zero questions, zero access tokens, and zero responses remaining in the database for that survey.

**Validates: Requirements 1.5**

---

### Property 4: Question blank text rejection

*For any* string that is empty or composed entirely of whitespace, attempting to create a Question with that text should be rejected at the model validation level and no Question row should be persisted.

**Validates: Requirements 2.2**

---

### Property 5: Response value range enforcement

*For any* integer outside the inclusive range [1, 5], attempting to create a Response with that value should be rejected by model validation. *For any* integer inside [1, 5], the Response should be accepted. This edge case includes boundary values 1 and 5 (valid) and 0 and 6 (invalid).

**Validates: Requirements 2.3, 4.7, 4.8**

---

### Property 6: Question cascade delete

*For any* question that has associated responses, deleting the question should result in zero responses remaining in the database for that question.

**Validates: Requirements 2.5**

---

### Property 7: Token length, URL-safety, and uniqueness

*For any* batch of N generated access tokens: every token should have length ≥ 32, every token should consist only of URL-safe characters (alphanumeric, `-`, `_`), and all N tokens should be pairwise distinct. Attempting to insert a duplicate token value should be rejected by the unique constraint.

**Validates: Requirements 3.2, 3.3, 3.5**

---

### Property 8: Valid unused token displays survey and all questions

*For any* survey with any number of questions and a valid unused access token, a GET request to `/survey/<token>/` should return HTTP 200 and the response body should contain the survey name and the text of every question belonging to that survey.

**Validates: Requirements 4.1**

---

### Property 9: Used token shows already-completed message

*For any* access token that has been marked as used, a GET request to `/survey/<token>/` should return HTTP 200 and the response body should contain the already-completed message, and should not contain a form submission element.

**Validates: Requirements 4.2**

---

### Property 10: Non-existent token returns 404

*For any* string that does not correspond to an existing access token, a GET request to `/survey/<string>/` should return HTTP 404.

**Validates: Requirements 4.3**

---

### Property 11: Valid partial submission records responses and marks token used

*For any* valid unused token and any non-empty subset of the survey's questions with valid (1–5) values, a POST to `/survey/<token>/` should: persist exactly the submitted response values, mark the token as used, and redirect to the confirmation page. Submitting an empty answer set (all questions skipped) should also succeed (partial responses permitted).

**Validates: Requirements 4.4, 4.5, 4.6**

---

### Property 12: Out-of-range submission is rejected

*For any* valid unused token and any response value outside [1, 5], a POST to `/survey/<token>/` should return a form with validation errors, leave the token unused, and persist no responses.

**Validates: Requirements 4.8**

---

### Property 13: Results counts accuracy

*For any* survey with any set of submissions, the results view should display, for each (question, value) pair, a count equal to the number of Response rows with that question and value. When no submissions exist, all counts should be zero (edge case). The total submission count should equal the number of access tokens with `used=True`.

**Validates: Requirements 5.2, 5.3, 5.4**

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Token not found | `get_object_or_404(AccessToken, token=token)` → HTTP 404 |
| Token already used | Render `already_used.html` with HTTP 200 |
| Invalid response value (form) | Re-render survey form with field-level error messages |
| Database connection failure | Django's default 500 handler; in production, gunicorn logs the traceback |
| Missing required env var at startup | `django-environ` raises `ImproperlyConfigured` — container exits with non-zero code, Fargate restarts it |
| Duplicate survey name | Django admin shows `IntegrityError` as a form validation error |
| Duplicate token (race condition) | `bulk_create` with `ignore_conflicts=False`; extremely unlikely given `secrets.token_urlsafe(32)` entropy |

---

## Testing Strategy

### Dual Testing Approach

Both unit tests and property-based tests are required. They are complementary:

- **Unit tests** cover specific examples, integration points, and error conditions.
- **Property-based tests** verify universal properties across randomly generated inputs, catching edge cases that hand-written examples miss.

### Property-Based Testing Library

Use **[Hypothesis](https://hypothesis.readthedocs.io/)** (Python) for all property-based tests.

```
hypothesis>=6.0
pytest-django
pytest
```

Each property test must run a minimum of **100 iterations** (Hypothesis default is 100; increase with `@settings(max_examples=200)` for critical properties).

Each property test must be tagged with a comment referencing the design property:

```python
# Feature: django-survey-app, Property 5: Response value range enforcement
@given(value=st.integers().filter(lambda x: x < 1 or x > 5))
def test_out_of_range_response_rejected(value):
    ...
```

### Property Tests (one per correctness property)

| Property | Test description | Hypothesis strategy |
|---|---|---|
| P1: Survey name uniqueness | Generate two surveys with same name; assert IntegrityError | `st.text(min_size=1)` for name |
| P2: Survey update round-trip | Create survey, update name/desc, read back, assert equality | `st.text`, `st.text` |
| P3: Survey cascade delete | Create survey with N questions/tokens/responses, delete, assert counts=0 | `st.integers(min_value=1, max_value=10)` for N |
| P4: Question blank text rejection | Attempt to create question with blank text; assert ValidationError | `st.text(alphabet=st.characters(whitelist_categories=('Zs',)))` |
| P5: Response value range | Out-of-range integers rejected; in-range accepted | `st.integers()` |
| P6: Question cascade delete | Create question with N responses, delete question, assert responses=0 | `st.integers(min_value=1, max_value=10)` |
| P7: Token properties | Generate N tokens; assert all len≥32, URL-safe, pairwise distinct | `st.integers(min_value=2, max_value=50)` for N |
| P8: Valid token GET | Create survey+questions+unused token, GET, assert 200 + all question texts | `st.lists(st.text(min_size=1), min_size=1)` for question texts |
| P9: Used token GET | Mark token used, GET, assert already-completed message present | — |
| P10: Invalid token 404 | Random string not in DB, GET, assert 404 | `st.text(min_size=1)` |
| P11: Partial submission | POST subset of questions with valid values, assert responses saved + token used | `st.lists` + `st.integers(1,5)` |
| P12: Out-of-range POST | POST with out-of-range value, assert form errors + token still unused | `st.integers().filter(lambda x: x < 1 or x > 5)` |
| P13: Results accuracy | Create N submissions with known values, GET results, assert counts match | `st.lists(st.integers(1,5))` |

### Unit Tests

Focus on specific examples and integration points:

- Admin action `generate_tokens` creates the requested number of tokens and associates them with the correct survey.
- Results view returns HTTP 403 / redirect for unauthenticated requests.
- `docker-compose.yml` and `Dockerfile` exist in the repository root.
- Settings reads `DATABASE_URL` from environment variables.
- `DEBUG=False` in environment sets `settings.DEBUG = False`.
- Survey form template includes a Bootstrap 5 CDN `<link>`.
- Results template wraps the table in a `table-responsive` div.
- Results view returns HTTP 200 for an authenticated staff user.

### Test Configuration

```ini
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = django_survey.settings
```

```python
# conftest.py
import django
from django.test import TestCase
# Use pytest-django fixtures: db, client, admin_client
```

Run tests with:
```
pytest --tb=short -q
```
