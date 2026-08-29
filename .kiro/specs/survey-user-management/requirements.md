# Requirements Document

## Introduction

This feature extends the existing Django Survey application so that authenticated users can own and manage their own surveys through a dedicated web UI (separate from Django admin). A user can create surveys and add questions to them, browse only the surveys they own, and issue access tokens for distribution. The survey list view surfaces token statistics (issued vs used) at a glance.

## Glossary

- **Survey_Owner**: An authenticated Django user (`django.contrib.auth.User`) who created a `Survey` instance.
- **Survey**: An existing model (`survey.Survey`) extended with a foreign key to `Survey_Owner`.
- **Question**: An existing model (`survey.Question`) with a foreign key to `Survey`.
- **AccessToken**: An existing model (`survey.AccessToken`) with a foreign key to `Survey` and a `used` boolean flag.
- **Survey_Management_UI**: The set of authenticated-user-facing views added by this feature (not the Django admin).
- **Token_Count**: The total number of `AccessToken` rows associated with a given `Survey`.
- **Used_Token_Count**: The number of `AccessToken` rows for a given `Survey` where `used = True`.

---

## Requirements

### Requirement 1: Survey Ownership

**User Story:** As an authenticated user, I want surveys to be linked to my account, so that I can manage only the surveys I have created.

#### Acceptance Criteria

1. THE `Survey` model SHALL include a non-nullable foreign key to `django.contrib.auth.User` representing the `Survey_Owner`.
2. WHEN a `Survey` instance is created through the `Survey_Management_UI`, THE `Survey` SHALL be associated with the currently authenticated user as its `Survey_Owner`.
3. IF the `Survey_Owner` account is deleted, THEN THE `Survey` instances owned by that user SHALL also be deleted (cascade).

---

### Requirement 2: Create Survey

**User Story:** As an authenticated user, I want to create new surveys, so that I can distribute them to respondents.

#### Acceptance Criteria

1. WHEN an authenticated user submits a valid create-survey form, THE `Survey_Management_UI` SHALL persist a new `Survey` instance with the submitted name and description and the current user as `Survey_Owner`.
2. WHEN an unauthenticated user attempts to access the create-survey page, THE `Survey_Management_UI` SHALL redirect the user to the login page.
3. IF a survey name is submitted that is empty or contains only whitespace, THEN THE `Survey_Management_UI` SHALL reject the submission and display a validation error.
4. IF a survey name is submitted that already exists in the database, THEN THE `Survey_Management_UI` SHALL reject the submission and display a uniqueness validation error.
5. WHEN a survey is created successfully, THE `Survey_Management_UI` SHALL redirect the user to the detail page for the newly created `Survey`.

---

### Requirement 3: Add Questions to a Survey

**User Story:** As an authenticated user, I want to add questions to a survey I own, so that respondents can answer them.

#### Acceptance Criteria

1. WHEN an authenticated user who is the `Survey_Owner` submits a valid add-question form for a `Survey`, THE `Survey_Management_UI` SHALL persist a new `Question` associated with that `Survey`.
2. WHEN an unauthenticated user attempts to access the add-question page, THE `Survey_Management_UI` SHALL redirect the user to the login page.
3. IF the question text submitted is empty or contains only whitespace, THEN THE `Survey_Management_UI` SHALL reject the submission and display a validation error.
4. IF an authenticated user who is NOT the `Survey_Owner` attempts to add a question to a `Survey`, THEN THE `Survey_Management_UI` SHALL return an HTTP 403 response.
5. WHEN a question is added successfully, THE `Survey_Management_UI` SHALL display the updated list of questions for that `Survey`.

---

### Requirement 4: Browse Owned Surveys

**User Story:** As an authenticated user, I want to see a list of all surveys I have created, so that I can manage them.

#### Acceptance Criteria

1. WHEN an authenticated user accesses the survey list page, THE `Survey_Management_UI` SHALL display only the `Survey` instances where the `Survey_Owner` matches the current user.
2. WHEN an unauthenticated user attempts to access the survey list page, THE `Survey_Management_UI` SHALL redirect the user to the login page.
3. THE `Survey_Management_UI` SHALL display the `Token_Count` alongside each `Survey` in the list.
4. THE `Survey_Management_UI` SHALL display the `Used_Token_Count` alongside each `Survey` in the list.
5. WHILE the authenticated user has no surveys, THE `Survey_Management_UI` SHALL display an empty-state message indicating that no surveys have been created yet.

---

### Requirement 5: Issue Access Tokens

**User Story:** As an authenticated user, I want to create access tokens for a survey I own, so that I can distribute them to respondents.

#### Acceptance Criteria

1. WHEN an authenticated user who is the `Survey_Owner` requests the creation of a new `AccessToken` for a `Survey`, THE `Survey_Management_UI` SHALL persist a new `AccessToken` associated with that `Survey`.
2. WHEN an unauthenticated user attempts to issue a token, THE `Survey_Management_UI` SHALL redirect the user to the login page.
3. IF an authenticated user who is NOT the `Survey_Owner` attempts to create a token for a `Survey`, THEN THE `Survey_Management_UI` SHALL return an HTTP 403 response.
4. WHEN an `AccessToken` is created successfully, THE `Survey_Management_UI` SHALL display the token value to the user so it can be distributed.
5. THE generated `AccessToken` SHALL have a token value with a minimum length of 32 characters consisting only of URL-safe characters (alphanumeric, `-`, `_`).

---

### Requirement 6: Survey Detail View

**User Story:** As an authenticated user, I want to view the detail page for a survey I own, so that I can see its questions and manage tokens.

#### Acceptance Criteria

1. WHEN an authenticated user who is the `Survey_Owner` accesses the survey detail page, THE `Survey_Management_UI` SHALL display the survey name, description, and all associated `Question` instances.
2. WHEN an unauthenticated user attempts to access the survey detail page, THE `Survey_Management_UI` SHALL redirect the user to the login page.
3. IF an authenticated user who is NOT the `Survey_Owner` attempts to access the survey detail page, THEN THE `Survey_Management_UI` SHALL return an HTTP 403 response.
4. THE survey detail page SHALL provide a control that allows the `Survey_Owner` to issue a new `AccessToken` for the `Survey`.
