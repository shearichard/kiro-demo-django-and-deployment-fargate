# Design Document

## Survey User Management

### Overview

This feature adds an authenticated survey management UI to the existing Django survey app. It extends the `Survey` model with an `owner` foreign key, and introduces a set of login-required views (list, create, detail, add-question, issue-token) that are scoped to the authenticated user's surveys. These management views live under a `/manage/` URL prefix and are entirely separate from the existing participant-facing views under `/survey/`.

The design follows the patterns already established in the codebase: function-based views with `@login_required`, Django forms for validation, and Bootstrap 5 templates that extend `base.html`.

---

### Architecture

```
django_survey/urls.py
  ├── /survey/<token>/          → existing participant views (survey/urls.py)
  ├── /survey/manage/           → new management views (survey/manage_urls.py)
  └── /health/                  → existing health check

survey/
  ├── models.py                 (Survey gets owner FK + migration)
  ├── manage_views.py           (new management views)
  ├── manage_urls.py            (new URL patterns under /manage/)
  ├── forms.py                  (extended with SurveyForm, QuestionForm)
  └── templates/survey/manage/
        ├── survey_list.html
        ├── survey_create.html
        ├── survey_detail.html
        ├── question_add.html
        └── token_created.html
```

The new `manage_views.py` module keeps management logic isolated from the existing participant-facing `views.py`. A dedicated `manage_urls.py` avoids polluting the existing `survey/urls.py` app namespace.

---

### Components and Interfaces

#### URL Patterns (`survey/manage_urls.py`, included at `/survey/manage/`)

| Name | Pattern | View |
|------|---------|------|
| `manage:survey_list` | `/survey/manage/surveys/` | `survey_list_view` |
| `manage:survey_create` | `/survey/manage/surveys/new/` | `survey_create_view` |
| `manage:survey_detail` | `/survey/manage/surveys/<int:pk>/` | `survey_detail_view` |
| `manage:question_add` | `/survey/manage/surveys/<int:pk>/questions/add/` | `question_add_view` |
| `manage:token_create` | `/survey/manage/surveys/<int:pk>/tokens/create/` | `token_create_view` |

All views are wrapped with `@login_required`. Ownership checks return HTTP 403 via `HttpResponseForbidden`.

#### Views (`survey/manage_views.py`)

```python
@login_required
def survey_list_view(request): ...

@login_required
def survey_create_view(request): ...

@login_required
def survey_detail_view(request, pk): ...

@login_required
def question_add_view(request, pk): ...

@login_required
def token_create_view(request, pk): ...
```

Each view that operates on a specific survey fetches it with `get_object_or_404(Survey, pk=pk)` then checks `survey.owner != request.user` and returns `HttpResponseForbidden()` if so.

#### Forms (`survey/forms.py` additions)

`SurveyForm` — `ModelForm` for `Survey`, fields: `name`, `description`. Reuses the existing `validate_not_blank` validator on `name`.

`QuestionForm` — `ModelForm` for `Question`, field: `text`. Reuses `validate_not_blank` via the model-level validator already on `Question.text`.

---

### Data Models

#### Migration strategy for `Survey.owner`

The `Survey` model has existing rows in production. The safest migration path is a two-step approach:

1. **Migration 1** — Add `owner` as nullable (`null=True, blank=True`) with `on_delete=CASCADE`. No default required; existing rows get `NULL`.
2. **Migration 2 (data migration)** — Assign a fallback owner to any existing surveys (e.g. the first superuser, or leave NULL if none exists). This avoids hard-coding a user ID.
3. **Migration 3** — Make `owner` non-nullable (`null=False`) once all rows have an owner.

In practice for this project (development/staging), a single migration with `null=True` followed by a manual data migration is acceptable. The design documents both options so the implementer can choose based on environment.

#### Updated `Survey` model

```python
class Survey(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='surveys',
        null=True,           # Temporary during migration; removed after data migration
    )
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

`settings.AUTH_USER_MODEL` is used instead of a hard import of `User` to follow Django best practices.

#### Existing models (unchanged)

- `Question` — unchanged; the FK to `Survey` means questions are implicitly owned via their survey.
- `AccessToken` — unchanged; the existing `generate_token()` already produces URL-safe 43-char tokens satisfying Requirement 5.5.
- `Response` — unchanged.

---

### Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Survey creation sets owner to current user

*For any* authenticated user and any valid (non-empty, non-duplicate) survey name + description, submitting the create-survey form should persist a `Survey` whose `owner` equals the submitting user.

**Validates: Requirements 1.2, 2.1**

---

### Property 2: Owner cascade delete removes surveys

*For any* user who owns N surveys, deleting that user should result in all N of those surveys also being deleted from the database.

**Validates: Requirements 1.3**

---

### Property 3: Whitespace-only name is rejected

*For any* string composed entirely of whitespace characters (including the empty string), submitting it as a survey name should fail form validation and no new `Survey` should be created.

**Validates: Requirements 2.3**

---

### Property 4: Duplicate survey name is rejected

*For any* survey name that already exists in the database, submitting that same name in the create-survey form should fail validation and no new `Survey` should be created.

**Validates: Requirements 2.4**

---

### Property 5: Whitespace-only question text is rejected

*For any* string composed entirely of whitespace characters (including the empty string), submitting it as a question text should fail form validation and no new `Question` should be created.

**Validates: Requirements 3.3**

---

### Property 6: Non-owner cannot add question (403)

*For any* survey and any authenticated user who is not the survey's owner, a POST request to the add-question endpoint for that survey should return HTTP 403 and no new `Question` should be created.

**Validates: Requirements 3.4**

---

### Property 7: Survey list is scoped to current user

*For any* authenticated user, the survey list view should return exactly the set of surveys owned by that user — no more, no fewer — regardless of how many surveys owned by other users exist in the database.

**Validates: Requirements 4.1**

---

### Property 8: Token statistics are accurate per survey

*For any* survey with T total tokens and U used tokens (0 ≤ U ≤ T), the survey list view context should expose `token_count = T` and `used_token_count = U` for that survey.

**Validates: Requirements 4.3, 4.4**

---

### Property 9: Non-owner cannot create token (403)

*For any* survey and any authenticated user who is not the survey's owner, a POST request to the token-create endpoint should return HTTP 403 and no new `AccessToken` should be created.

**Validates: Requirements 5.3**

---

### Property 10: Generated tokens are URL-safe and at least 32 characters

*For any* call to `generate_token()`, the returned string should have length ≥ 32 and contain only URL-safe characters (alphanumeric characters, `-`, `_`).

**Validates: Requirements 5.5**

---

### Property 11: Non-owner cannot view survey detail (403)

*For any* survey and any authenticated user who is not the survey's owner, a GET request to the survey detail endpoint should return HTTP 403.

**Validates: Requirements 6.3**

---

## Error Handling

| Scenario | Handling |
|----------|---------|
| Unauthenticated access to any management URL | `@login_required` redirects to `settings.LOGIN_URL` (Django default: `/accounts/login/`) |
| Non-owner attempts ownership-gated action | Return `HttpResponseForbidden()` (HTTP 403) |
| Survey not found (invalid PK) | `get_object_or_404` returns HTTP 404 |
| Form submission with validation errors | Re-render the form template with error messages inline |
| Duplicate survey name | ModelForm surfaces the `unique` constraint as a form error on the `name` field |
| Blank/whitespace name or question text | `validate_not_blank` raises `ValidationError`; form surfaces the message |

No custom exception middleware is needed. All error paths use standard Django response primitives.

---

## Testing Strategy

### Dual testing approach

Unit tests (using Django's `TestCase`) cover specific examples, integration flows, and edge cases. Property-based tests (using **Hypothesis** with `hypothesis-django`) cover the universally-quantified properties above across many generated inputs.

### Unit test coverage

- GET/POST for each management view with authenticated owner, unauthenticated user, and non-owner user
- Survey list shows correct surveys and correct counts
- Empty-state rendering when user has no surveys
- Redirect to detail after successful survey creation
- Detail page renders questions and token-creation control
- Token value displayed in response after creation

### Property-based test configuration

Library: **Hypothesis** (`pip install hypothesis`)  
Minimum iterations: 100 per property (Hypothesis default `max_examples=100`)  
Each property test must include a comment referencing the design property number and text.

Tag format in test docstring:
```
# Feature: survey-user-management, Property <N>: <property_text>
```

Each correctness property above maps to exactly one Hypothesis `@given(...)` test. Hypothesis strategies to use:

- `st.text(min_size=1)` for valid survey names / question texts (filtered to non-whitespace)
- `st.text()` + `st.text(alphabet=string.whitespace)` for blank/whitespace inputs
- `st.integers(min_value=0, max_value=50)` for token counts
- Django model factories (via `hypothesis.extra.django`) for generating `User` and `Survey` instances

### Test file structure

```
survey/tests/
  test_manage_views.py       # unit tests for all management views
  test_manage_forms.py       # unit tests for SurveyForm and QuestionForm
  test_manage_properties.py  # Hypothesis property-based tests
  test_token_generation.py   # unit + property tests for generate_token()
```
