# Requirements Document

## Introduction

A Django + PostgreSQL web application that allows administrators to create surveys with 1–5 scale questions, distribute unique per-participant URLs, and view aggregated results. The app is containerised with Docker Compose for local development (using a Postgres container) and is designed to be deployed on AWS Fargate with Amazon RDS PostgreSQL as the production database backend.

## Glossary

- **Admin**: A Django superuser or staff user with access to the Django admin interface
- **Survey**: A named collection of one or more questions created by an Admin
- **Question**: A single survey item that a Participant answers on a scale of 1 to 5
- **Participant**: An individual who has been issued a unique access token to take part in a specific Survey
- **Access_Token**: A unique, single-use URL token issued by an Admin that grants one Participant access to one Survey
- **Response**: A Participant's answer to a single Question (an integer value between 1 and 5 inclusive)
- **Submission**: The act of a Participant saving their answers for a Survey; marks the Access_Token as used
- **Results_View**: An admin-facing page showing aggregated Response counts per Question per Survey
- **System**: The Django survey web application

---

## Requirements

### Requirement 1: Survey Management

**User Story:** As an Admin, I want to create and manage surveys, so that I can organise questions into distinct survey campaigns.

#### Acceptance Criteria

1. THE System SHALL allow an Admin to create a Survey with a unique name and an optional description via the Django admin interface.
2. THE System SHALL allow an Admin to update the name and description of an existing Survey via the Django admin interface.
3. THE System SHALL allow an Admin to delete a Survey via the Django admin interface.
4. THE System SHALL support multiple Surveys existing in an active state simultaneously.
5. WHEN an Admin deletes a Survey, THE System SHALL also delete all Questions, Access_Tokens, and Responses associated with that Survey.

---

### Requirement 2: Question Management

**User Story:** As an Admin, I want to add scale questions to a survey, so that participants can rate items on a 1–5 scale.

#### Acceptance Criteria

1. THE System SHALL allow an Admin to add one or more Questions to a Survey via the Django admin interface.
2. THE System SHALL require each Question to have a non-empty text field describing what is being rated.
3. THE System SHALL restrict valid Response values for every Question to integers in the range 1 to 5 inclusive.
4. THE System SHALL allow an Admin to remove a Question from a Survey via the Django admin interface.
5. WHEN an Admin removes a Question, THE System SHALL also delete all Responses associated with that Question.

---

### Requirement 3: Access Token Generation

**User Story:** As an Admin, I want to generate unique URLs for individual participants, so that each person gets their own controlled access to a specific survey.

#### Acceptance Criteria

1. THE System SHALL allow an Admin to generate one or more Access_Tokens for a given Survey via the Django admin interface.
2. THE System SHALL generate each Access_Token as a cryptographically random value of at least 32 characters.
3. THE System SHALL associate each Access_Token with exactly one Survey and at most one Participant identity.
4. THE System SHALL expose each Access_Token as a unique URL that a Participant can visit to access the associated Survey.
5. THE System SHALL allow an Admin to generate multiple Access_Tokens for the same Survey to accommodate multiple Participants.

---

### Requirement 4: Survey Participation

**User Story:** As a Participant, I want to access and complete a survey using my unique URL, so that I can submit my responses.

#### Acceptance Criteria

1. WHEN a Participant visits a valid, unused Access_Token URL, THE System SHALL display the associated Survey and all of its Questions.
2. WHEN a Participant visits an Access_Token URL that has already been used for a Submission, THE System SHALL display a message indicating the survey has already been completed and SHALL NOT allow further responses.
3. WHEN a Participant visits an Access_Token URL that does not exist, THE System SHALL return an HTTP 404 response.
4. THE System SHALL allow a Participant to submit a Submission containing answers to any subset of Questions (partial responses are permitted).
5. WHEN a Participant submits a Submission, THE System SHALL record each provided Response and SHALL mark the Access_Token as used.
6. WHEN a Participant submits a Submission, THE System SHALL display a confirmation message indicating the submission was received.
7. THE System SHALL validate that any provided Response value is an integer between 1 and 5 inclusive before recording it.
8. IF a Participant submits a Response value outside the range 1 to 5, THEN THE System SHALL reject the Submission and display a descriptive validation error.

---

### Requirement 5: Results Aggregation

**User Story:** As an Admin, I want to see aggregated results for a survey, so that I can understand how participants responded to each question.

#### Acceptance Criteria

1. THE System SHALL provide a Results_View accessible to Admins for each Survey.
2. THE Results_View SHALL display, for each Question in the Survey, the count of Responses for each value 1 through 5.
3. THE Results_View SHALL display the total number of Submissions received for the Survey.
4. WHEN no Submissions have been recorded for a Survey, THE Results_View SHALL display zero counts for all Questions and values.
5. THE Results_View SHALL present data in a tabular format without requiring chart or visualisation rendering.

---

### Requirement 6: Containerisation and Local Development

**User Story:** As a developer, I want to run the application locally using Docker Compose, so that I can develop and test without a cloud environment.

#### Acceptance Criteria

1. THE System SHALL include a `docker-compose.yml` file that defines a service for the Django application and a service for a PostgreSQL database container.
2. WHEN the Docker Compose stack is started, THE System SHALL be accessible on a defined local port without additional manual configuration.
3. THE System SHALL read database connection parameters (host, port, name, user, password) from environment variables so that the same container image can connect to either the local Postgres container or Amazon RDS.
4. THE System SHALL include a `Dockerfile` that produces a self-contained image of the Django application suitable for deployment on AWS Fargate.
5. THE System SHALL use a `requirements.txt` file to declare all Python dependencies so that the Docker image build is reproducible.

---

### Requirement 7: Production Deployment Readiness

**User Story:** As a developer, I want the application to be deployable on AWS Fargate with Amazon RDS PostgreSQL, so that I can run the demo in a cloud environment.

#### Acceptance Criteria

1. THE System SHALL read all sensitive configuration values (secret key, database credentials, allowed hosts) from environment variables rather than hard-coded values.
2. THE System SHALL support running Django database migrations as a step that can be executed inside the container before the application starts.
3. THE System SHALL serve static files in a manner compatible with containerised deployment (e.g. collected into a single directory via `collectstatic`).
4. WHEN the `DEBUG` environment variable is set to `False`, THE System SHALL operate in production mode with Django's debug features disabled.

---

### Requirement 8: Responsive UI

**User Story:** As a Participant or Admin, I want the application's pages to be usable on both mobile phones and laptops, so that I can access surveys and results regardless of my device.

#### Acceptance Criteria

1. THE System SHALL include Bootstrap 5 as the front-end CSS and JavaScript framework for all participant-facing and admin-results pages.
2. THE System SHALL render participant-facing Survey pages using a responsive layout that adapts to screen widths from 320px (mobile) up to desktop viewport sizes.
3. THE System SHALL render the Results_View using a responsive layout that remains readable and usable on both mobile and desktop screen sizes.
4. WHEN a Participant accesses a Survey page on a mobile device, THE System SHALL display all Questions and the submission control without requiring horizontal scrolling.
5. WHEN an Admin accesses the Results_View on a mobile device, THE System SHALL display the results table in a manner that does not require horizontal scrolling to read Question text and Response counts.
