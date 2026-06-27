# BIOMAPS Survey Automation

Five AWS Lambda functions that automate the BIOMAPS assessment survey lifecycle — survey creation, date management, scheduled reminders, and scored data uploads to S3 — integrated with Qualtrics and a Streamlit dashboard.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Lambda Functions — Detailed Reference](#lambda-functions--detailed-reference)
- [S3 Buckets](#s3-buckets)
- [Qualtrics Workflows](#qualtrics-workflows)
- [Environment Variables — Complete Reference](#environment-variables--complete-reference)
- [Deployment Notes](#deployment-notes)
- [Typical Survey Lifecycle](#typical-survey-lifecycle)
- [Troubleshooting](#troubleshooting)

---

## Overview

This system automates the lifecycle of BIOMAPS (Biology Measuring Achievement and Progression of Students) assessment surveys. It consists of five AWS Lambda functions that interact with the Qualtrics survey platform, store tracking and results data in Amazon S3, and ultimately feed a Streamlit dashboard used for data exploration and reporting.

The four supported assessment types are:

| Assessment | Full Name |
|------------|-----------|
| **GenBio-MAPS** | General biology |
| **EcoEvo-MAPS** | Ecology and evolution |
| **Phys-MAPS** | Physiology |
| **Capstone** | Molecular biology capstone |

---

## Architecture

```
Instructor (via Qualtrics / API)
        │
        ▼
┌───────────────────────┐
│  createBIOMAPSSurvey  │──── Creates a new survey from QSF template in Qualtrics
└───────────────────────┘
        │
        ▼
┌────────────────────────────┐
│  update_inprogressBIOMAPS  │──── Adds class to in-progress tracking CSV in S3
└────────────────────────────┘
        │
        ▼
┌──────────────────────┐
│  changeBIOMAPSDates  │──── Lets instructors change close dates / reminders
└──────────────────────┘
        │
        ▼
┌───────────────────┐
│  automateBIOMAPS  │──── Monitors active surveys: sends reminders, closes surveys,
└───────────────────┘     triggers data upload when surveys close
        │                 (runs on a schedule via EventBridge)
        ▼
┌──────────────────────────────┐
│  uploadBIOMAPSDashboardData  │──── Scores responses, uploads results to S3
└──────────────────────────────┘
        │
        ▼
   S3 Dashboard Bucket  ──── Consumed by Streamlit dashboard
```

### How Data Flows

1. An instructor fills out the **Course Information Survey (CIS)** in Qualtrics, providing course details.
2. **createBIOMAPSSurvey** generates a new assessment survey from the appropriate QSF template and returns a survey link.
3. **update_inprogressBIOMAPS** adds the instructor's class ID to a tracking CSV in S3 so the automation knows to monitor it.
4. **changeBIOMAPSDates** allows instructors to adjust their survey close date or toggle reminders on/off.
5. **automateBIOMAPS** runs on a schedule (via AWS EventBridge). Each invocation, it reads the in-progress CSV and checks one active survey:
   - If the close date is within 4 days and reminders are enabled, it sends a reminder email.
   - If the close date has passed, it closes the survey in Qualtrics, triggers data upload, and sends a report-ready email.
6. **uploadBIOMAPSDashboardData** downloads all responses from Qualtrics, validates them (consent, age, completeness), scores them against answer keys, labels demographics, and uploads the processed data to the dashboard S3 bucket.
7. The **Streamlit dashboard** reads the processed CSV files from S3 to display results.

---

## Lambda Functions — Detailed Reference

### 1. automateBIOMAPS

**Trigger:** Scheduled (AWS EventBridge / CloudWatch Events)

**Purpose:** The core automation engine. Runs periodically to monitor all active surveys and take action based on their close dates. Processes one survey per invocation to stay within Lambda time limits and avoid overloading the Qualtrics API.

**What it does each invocation:**
1. Downloads the in-progress CSV from S3 to get the list of active class IDs.
2. Iterates through class IDs and retrieves each instructor's CIS response from Qualtrics.
3. Checks the survey close date against today:
   - **Close date has passed** → Closes the survey in Qualtrics, invokes `uploadBIOMAPSDashboardData` logic, sends a "report ready" email, updates the CIS response with timestamps.
   - **Close date is within 4 days** → Sends a reminder email (if reminders are enabled), updates the CIS response to record that the reminder was sent.
4. Stops after handling one action to keep execution time low.

**Source files:**

| File | Purpose |
|------|---------|
| `lambda_function.py` | Main handler — reads in-progress CSV, date logic, orchestration |
| `utilities/qualtrics_utils.py` | `get_response_count()`, `get_response_data()`, `update_response_data()`, `close_survey()` |
| `utilities/email_utils.py` | `send_email()`, `build_email()` — constructs and sends emails via Qualtrics |
| `utilities/reminder.txt` | Email template for survey reminders (includes response count, close date, survey link) |
| `utilities/report_sent.txt` | Email template for report-ready notification (includes dashboard link) |

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `QUALTRICS_API_TOKEN` | API token for authenticating with Qualtrics |
| `QUALTRICS_BASE_URL` | Qualtrics datacenter base URL (i.e., `https://yul1.qualtrics.com`) |
| `CIS_SURVEY_ID` | Survey ID of the Course Information Survey in Qualtrics |
| `EXPECTED_TOKEN` | Shared API key used to authenticate inter-service calls |
| `INPROGRESS_BUCKET_NAME` | S3 bucket name containing the in-progress tracking CSV |
| `INPROGRESS_FILE_NAME` | Filename of the in-progress CSV (i.e., `in_progress.csv`) |
| `EMAIL_REQUEST_URL` | Endpoint for sending emails via Qualtrics distributions |

---

### 2. createBIOMAPSSurvey

**Trigger:** API Gateway (HTTP POST)

**Purpose:** Creates a new BIOMAPS assessment survey in Qualtrics from a predefined template (QSF file). Returns the new survey's ID and link so the instructor can distribute it to students.

**What it does:**
1. Validates the API token from request headers.
2. Extracts survey parameters from the request body: institution, course number, instructor last name, survey type, and instructor ID.
3. Sanitizes all text inputs (normalizes Unicode, removes special characters, replaces spaces with underscores).
4. Generates a survey title in the format: `{year}_{institution}_{courseNumber}_{lastName}_{surveyType}_{instructorId}`
5. Loads the appropriate QSF template file based on survey type.
6. Uploads the QSF to Qualtrics via the Import Survey API endpoint.
7. Activates the newly created survey.
8. Returns the survey ID and a direct survey link.

**Request body fields:**

| Field | Description | Example |
|-------|-------------|---------|
| `institution` | Name of the institution | `"University of Colorado"` |
| `number` | Course number or identifier | `"BIO101"` |
| `instructor_last` | Instructor's last name | `"Smith"` |
| `survey_type` | One of: `GenBio-MAPS`, `EcoEvo-MAPS`, `Phys-MAPS`, `Capstone` | `"GenBio-MAPS"` |
| `instructor_id` | Unique instructor identifier from CIS | `"R_abc123"` |

**Source files:**

| File | Purpose |
|------|---------|
| `lambda_function.py` | Main handler — input validation, Qualtrics API calls, survey creation |
| `GenBio-MAPS.qsf` | QSF template for GenBio-MAPS assessments (largest template) |
| `EcoEvo-MAPS.qsf` | QSF template for EcoEvo-MAPS assessments |
| `Phys-MAPS.qsf` | QSF template for Phys-MAPS assessments |
| `Capstone.qsf` | QSF template for Capstone assessments |

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `QUALTRICS_API_TOKEN` | API token for authenticating with Qualtrics |
| `QUALTRICS_BASE_URL` | Qualtrics datacenter base URL |
| `CIS_SURVEY_ID` | Course Information Survey ID |
| `EXPECTED_TOKEN` | API key for request validation |

---

### 3. changeBIOMAPSDates

**Trigger:** API Gateway (HTTP POST)

**Purpose:** Allows instructors to modify the close date and reminder preferences for their active survey. If the survey was previously closed, this function reactivates it.

**What it does:**
1. Validates the API token from request headers.
2. Extracts the instructor ID, new close date, and reminder preference from the request body.
3. Looks up the instructor's CIS response in Qualtrics to get the associated survey ID.
4. Updates the CIS response's embedded data fields:
   - Sets the new "Survey Close Date."
   - Sets the reminder preference ("Yes" or "No").
5. If the survey was closed (inactive), reactivates it via the Qualtrics API.
6. Adds the class ID to the in-progress tracking CSV in S3 (if not already present).
7. Returns instructor details and confirmation of updates.

**Request body fields:**

| Field | Description |
|-------|-------------|
| `instructor_id` | Instructor's CIS response ID |
| `close_date` | New survey close date |
| `reminder` | Whether to send reminders (`"Yes"` or `"No"`) |

**Source files:**

| File | Purpose |
|------|---------|
| `lambda_function.py` | Main handler — date updates, survey reactivation, CSV tracking |

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `QUALTRICS_API_TOKEN` | API token for authenticating with Qualtrics |
| `QUALTRICS_BASE_URL` | Qualtrics datacenter base URL |
| `CIS_SURVEY_ID` | Course Information Survey ID |
| `EXPECTED_TOKEN` | API key for request validation |
| `INPROGRESS_BUCKET_NAME` | S3 bucket for in-progress tracking |
| `INPROGRESS_FILE_NAME` | In-progress CSV filename |

---

### 4. update_inprogressBIOMAPS

**Trigger:** API Gateway (HTTP POST)

**Purpose:** Manually adds a class/instructor to the in-progress tracking CSV. Used when a survey is created or managed outside the normal automated workflow and needs to be picked up by `automateBIOMAPS`.

**What it does:**
1. Validates the API token from request headers.
2. Extracts the instructor ID from the request body.
3. Downloads the in-progress CSV from S3.
4. Checks if the class ID already exists (skips if duplicate).
5. Appends the new class ID as a row.
6. Uploads the updated CSV back to S3.

**Request body fields:**

| Field | Description |
|-------|-------------|
| `instructor_id` | Instructor's CIS response ID to add to tracking |

**Source files:**

| File | Purpose |
|------|---------|
| `lambda_function.py` | Main handler — CSV read/update/upload logic |

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `EXPECTED_TOKEN` | API key for request validation |
| `CIS_SURVEY_ID` | Course Information Survey ID |
| `INPROGRESS_BUCKET_NAME` | S3 bucket for in-progress tracking |
| `INPROGRESS_FILE_NAME` | In-progress CSV filename |

---

### 5. uploadBIOMAPSDashboardData

**Trigger:** API Gateway (HTTP POST) or called internally by `automateBIOMAPS`

**Purpose:** The data processing pipeline. Downloads raw survey responses from Qualtrics, validates and filters them, scores student answers against answer keys, labels demographic data, and uploads the processed results to S3 for the Streamlit dashboard.

**What it does:**
1. Validates the API token from request headers.
2. Retrieves the instructor's CIS response to determine the survey ID, survey type, course type, and class size.
3. Exports survey responses from Qualtrics (creates export, polls until complete, downloads ZIP, extracts CSV).
4. Validates responses:
   - Removes students who did not consent.
   - Removes students under 18.
   - Keeps only completed surveys (`Finished == 1`).
   - Removes duplicate student entries (by name and ID).
   - Drops responses missing identification info.
5. Scores each student's responses against the answer key for the assessment type:
   - Marks each item as correct (1) or incorrect (0).
   - Calculates a total score as a percentage.
   - Scores "constructs" (thematic groupings of questions).
   - Special handling for GenBio-MAPS: accounts for randomized question blocks where some questions may not be presented.
6. Labels demographic data:
   - Gender (Male/Female)
   - URM status (Underrepresented Minority / Majority)
   - Class standing (Freshman through Graduate)
   - Major (Biology/Life Sciences vs. Other)
   - Transfer status
   - English Language Learner status
   - First-generation college student status
7. Reorders and filters columns based on a header ordering CSV specific to the assessment type.
8. Uploads the processed DataFrame to S3:
   - Filename format: `{survey_type}_DashboardData_{year}.csv`
   - Appends to existing data if the file already exists.
   - Removes duplicate Class_ID entries to handle survey reopenings cleanly.
9. Removes the class ID from the in-progress tracking CSV.

**Source files:**

| File | Purpose |
|------|---------|
| `lambda_function.py` | Main handler — orchestration, S3 upload, in-progress cleanup |
| `utilities/compiling_utils.py` | `compile_course_data()` — orchestrates the full data pipeline |
| `utilities/qualtrics_utils.py` | `get_cis_response_data()`, `download_responses_as_df()` — Qualtrics data retrieval |
| `utilities/scoring_utils.py` | `validate_responses()`, `score_biomaps()` — response validation and scoring |
| `utilities/processing_utils.py` | `process_names()`, `label_demographics()`, `simplify_columns()` — data cleanup and labeling |
| `utilities/AssessmentSolutions/{Type}_Solutions.csv` | Answer keys for each assessment type |
| `utilities/AssessmentSolutions/{Type}_Constructs.csv` | Construct (question grouping) definitions |
| `utilities/ColumnOrdering/{Type}_Headers.csv` | Final column ordering for dashboard output |

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `QUALTRICS_API_TOKEN` | API token for authenticating with Qualtrics |
| `QUALTRICS_BASE_URL` | Qualtrics datacenter base URL |
| `CIS_SURVEY_ID` | Course Information Survey ID |
| `EXPECTED_TOKEN` | API key for request validation |
| `DASHBOARD_BUCKET_NAME` | S3 bucket where processed dashboard data is stored |
| `INPROGRESS_BUCKET_NAME` | S3 bucket for in-progress tracking |
| `INPROGRESS_FILE_NAME` | In-progress CSV filename |

---

## S3 Buckets

| Bucket (env var) | Contents | Used By |
|------------------|----------|---------|
| `INPROGRESS_BUCKET_NAME` | `in_progress.csv` — tracks active class IDs with surveys currently open | automateBIOMAPS (read), changeBIOMAPSDates (write), update_inprogressBIOMAPS (write), uploadBIOMAPSDashboardData (write) |
| `DASHBOARD_BUCKET_NAME` | `{SurveyType}_DashboardData_{Year}.csv` — scored and processed survey results | uploadBIOMAPSDashboardData (write), Streamlit dashboard (read) |

### In-Progress CSV Format

| Column | Description |
|--------|-------------|
| `Class_ID` | The instructor's CIS response ID, used to look up all related survey data |

### Dashboard CSV Format

The output columns vary by assessment type but generally include:

- `Class_ID` — Identifier linking to the CIS response
- `Class_Size` — Reported class enrollment
- `Class_Level` — Introductory, Upper-level, or Graduate
- Student identification fields (ID, name)
- Demographic labels (Gender, URM status, Class standing, Major, Transfer, ELL, First-gen)
- Individual item scores (1 = correct, 0 = incorrect)
- Construct scores (percentage correct within each question grouping)
- `Total_Score` — Overall percentage correct

---

## Qualtrics Workflows

### Course Information Survey (CIS)

The CIS is a central Qualtrics survey that stores instructor and course metadata as embedded data fields. Its survey ID is configured via the `CIS_SURVEY_ID` environment variable. Every function references the CIS to look up or update instructor data.

Key embedded data fields stored in CIS responses:

| Field | Description |
|-------|-------------|
| Survey ID | The Qualtrics survey ID for the instructor's assessment |
| Survey Type | Which BIOMAPS assessment (GenBio-MAPS, EcoEvo-MAPS, Phys-MAPS, Capstone) |
| Course Type | Level of the course |
| Class Size | Number of students enrolled |
| Survey Close Date | When the survey should be closed |
| Reminder | Whether reminders are enabled ("Yes"/"No") |
| Instructor email | Used for sending notifications |

### API Authentication

All Qualtrics API calls use a bearer token (`QUALTRICS_API_TOKEN`) in the `X-API-TOKEN` header. The base URL (`QUALTRICS_BASE_URL`) varies by Qualtrics datacenter.

### Inter-Function Authentication

All Lambda functions validate incoming requests using a shared token (`EXPECTED_TOKEN`) passed in the request headers. Requests without a valid token are rejected with a 401 response.

### Qualtrics Workflows

Two workflows are configured in Qualtrics on the Course Information Survey (CIS). These orchestrate the handoff between Qualtrics and the AWS Lambda functions.

#### Workflow 1: "Create Requested Survey" (Triggered on CIS Submission)

**Trigger:** A new response is created on `Course_Information_Survey_v2` (newly created responses only — not API updates, imports, or incomplete responses).

This workflow runs automatically when an instructor submits the CIS, kicking off the full survey creation pipeline:

```
Instructor submits CIS
        │
        ▼
┌───────────────────────────────────────┐
│  T-ID 1: Create Survey Using AWS      │
│  POST → createBIOMAPSSurvey           │
│  Sends: Institution, InstructorLast,  │
│    Instructor_ID, Number, SurveyType  │
│  Returns: surveyId, surveyLink        │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  T-ID 5: Add course ID to InProgress  │
│  POST → update_inprogressBIOMAPS      │
│  Sends: Instructor_ID                 │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  T-ID 3: Send Email                                   │
│  To: Instructor email                                 │
│  From: BIOMAPS@cornell.edu                            │
│  Subject: "{Survey Type} Survey link ({ResponseID})"  │
│  Body: Survey link + instructions to share            │
│    with students ≥7 days before close date            │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  T-ID 4: Update Response's Embedded Data  │
│  PUT → Qualtrics API                      │
│  Sets "Survey ID" and "Survey Sent" date  │
│  on the instructor's CIS response         │
└───────────────────────────────────────────┘
```

**Task details:**

| Step | Type | Target | What it does |
|------|------|--------|-------------|
| T-ID 1 | WebService (POST) | `createBIOMAPSSurvey` Lambda | Passes CIS answers (institution, instructor last name, course number, survey type, instructor ID) to create the survey. Returns `surveyId` and `surveyLink`, which are piped into later tasks. |
| T-ID 5 | WebService (POST) | `update_inprogressBIOMAPS` Lambda | Passes the instructor's Response ID as `Instructor_ID` to add the class to the in-progress tracking CSV. |
| T-ID 3 | Email | Instructor | Sends the survey link and close date to the instructor (see full template below). |
| T-ID 4 | WebService (PUT) | Qualtrics API (`/API/v3/responses/{ResponseID}`) | Updates the CIS response's embedded data with the new `Survey ID` (from T-ID 1) and sets `Survey Sent` to the current date. |

**T-ID 3 email template (sent to instructor on CIS submission):**

> Dear {First Name} {Last Name},
>
> Thank you for participating in the {Survey Type} survey. Below is the link to the survey for your course, {Course Name} ({Course Number}):
>
> {Survey Link}
>
> Please share this link with your students at least 7 days before the close date listed below.
>
> This link is currently active and will remain active until:
> {Close Date}
>
> If you would like to change the date that the survey will stop accepting responses from students, please complete the form here with your unique ResponseID ({ResponseID}):
>
> https://cornell.ca1.qualtrics.com/jfe/form/SV_3TTUJMbWVDZ2aKG
>
> Let us know by replying to this email if you have any questions about this process.
>
> Thank you,
> BIOMAPS
>
> This message was sent by an automated system.

#### Workflow 2: "Send Requested Email" (Triggered by AWS)

**Trigger:** JSON inbound event via trigger URL (called by `automateBIOMAPS` Lambda).

This is a simple email relay — the Lambda constructs the full email content and posts it to the Qualtrics trigger URL, which sends the email.

```
automateBIOMAPS Lambda
        │
        ▼
┌───────────────────────────┐
│  JSON Trigger             │
│  Receives: emailAddress,  │
│  emailSubject, emailBody  │
└───────────────────────────┘
        │
        ▼
┌────────────────────────────────┐
│  T-ID 1: Send Requested Email  │
│  From: BIOMAPS@cornell.edu     │
│  To/Subject/Body from trigger  │
└────────────────────────────────┘
```

| Field | Source |
|-------|--------|
| **Trigger URL** | `EMAIL_REQUEST_URL` environment variable in `automateBIOMAPS` |
| **To** | `emailAddress` from JSON payload |
| **Subject** | `emailSubject` from JSON payload |
| **Body** | `emailBody` from JSON payload |
| **From** | BIOMAPS@cornell.edu (display name: "BIOMAPS") |
| **Reply-To** | BIOMAPS@cornell.edu |

This workflow is used to send both **survey reminder emails** (when the close date is within 4 days) and **report-ready emails** (when the survey closes and data is uploaded). The email templates are defined in `automateBIOMAPS/utilities/reminder.txt` and `automateBIOMAPS/utilities/report_sent.txt`.

#### Workflow 3: "Update Close Dates, Update CIS, and Send Email" (on BIOMAPS_Date_Changes survey)

**Trigger:** A new response is created on `BIOMAPS_Date_Changes` (newly created responses only).

This workflow runs when an instructor submits the date change form to request a new survey close date or update their reminder preference. It calls the `changeBIOMAPSDates` Lambda, updates the CIS embedded data, and sends a confirmation email — but only if the change is valid.

```
Instructor submits BIOMAPS_Date_Changes form
(provides ResponseID, new close date, reminder preference)
        │
        ▼
┌───────────────────────────────────────────┐
│  T-ID 1: Initiate necessary changes       │
│  POST → changeBIOMAPSDates Lambda         │
│  Sends: Instructor_ID, Requested Survey   │
│    Close Date, Requested Survey Reminder  │
│  Returns: Email, Course Name, Course      │
│    Number, Instructor name, Survey Type,  │
│    JSON Request, Update Possible          │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  T-ID 2: Update CIS Response's        │
│  Embedded Data                        │
│  PUT → Qualtrics API                  │
│  Updates the CIS response with the    │
│  JSON Request from T-ID 1 (new close  │
│  date and reminder settings)          │
└───────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────┐
│  Decision: Survey change requested         │
│  is valid                                  │
│  Continues ONLY if T-ID 1 returned         │
│  "Update Possible" == true                 │
│  (otherwise workflow ends, no email sent)  │
└────────────────────────────────────────────┘
        │ (if valid)
        ▼
┌──────────────────────────────────────┐
│  T-ID 3: Send confirmation email     │
│  To: Instructor email (from T-ID 1)  │
│  From: BIOMAPS@cornell.edu           │
│  Confirms new close date             │
└──────────────────────────────────────┘
```

**Task details:**

| Step | Type | Target | What it does |
|------|------|--------|-------------|
| T-ID 1 | WebService (POST) | `changeBIOMAPSDates` Lambda | Sends the instructor's Response ID, requested close date, and reminder preference. Returns instructor details (name, email, course info, survey type), a JSON Request payload for updating the CIS, and an `Update Possible` flag. |
| T-ID 2 | WebService (PUT) | Qualtrics API (`/API/v3/responses/{ResponseID}`) | Updates the CIS response's embedded data using the `JSON Request` returned by T-ID 1 (sets new Survey Close Date and Survey Reminder). |
| Decision | Conditional | — | Checks if `Update Possible` from T-ID 1 equals `true`. If not, the workflow ends without sending an email (e.g., if the Response ID was invalid). |
| T-ID 3 | Email | Instructor | Sends a confirmation email with the new close date (see template below). |

**T-ID 3 email template (sent to instructor on date change):**

> Dear {Instructor First} {Instructor Last},
>
> Thank you again for participating in the {Survey Type} survey. Changes were recently made to the close date for your class, {Course Name} ({Course Number}). This survey is currently set to close for students on the following date (yyyy/mm/dd):
>
> {New Close Date}
>
> If you would like to change this date again, please fill out the form again with your unique ResponseID ({ResponseID}):
>
> https://cornell.ca1.qualtrics.com/jfe/form/SV_3TTUJMbWVDZ2aKG
>
> Thank you,
> BIOMAPS
>
> This message was sent by an automated system.

---

## Environment Variables — Complete Reference

| Variable | Used By | Description |
|----------|---------|-------------|
| `QUALTRICS_API_TOKEN` | All except update_inprogress | Qualtrics API authentication token |
| `QUALTRICS_BASE_URL` | All except update_inprogress | Qualtrics datacenter URL |
| `CIS_SURVEY_ID` | All | Course Information Survey ID in Qualtrics |
| `EXPECTED_TOKEN` | All | Shared API key for request authentication |
| `INPROGRESS_BUCKET_NAME` | automate, changeDates, update_inprogress, uploadDashboard | S3 bucket for in-progress tracking |
| `INPROGRESS_FILE_NAME` | automate, changeDates, update_inprogress, uploadDashboard | Filename of the tracking CSV |
| `DASHBOARD_BUCKET_NAME` | uploadDashboard | S3 bucket for processed dashboard data |
| `EMAIL_REQUEST_URL` | automate | Qualtrics email distribution endpoint |

---

## Deployment Notes

- Each Lambda function is deployed as a self-contained package that includes its source code and all Python dependencies (notably `requests`, `boto3`, `urllib3`, `certifi`) bundled in the deployment ZIP.
- The QSF template files for `createBIOMAPSSurvey` are included in the deployment package alongside the handler.
- The answer key CSVs and column ordering CSVs for `uploadBIOMAPSDashboardData` are bundled inside the `utilities/` directory.
- `automateBIOMAPS` must have an EventBridge (CloudWatch Events) rule configured as its trigger to run on a recurring schedule.
- The four API-triggered functions (`createBIOMAPSSurvey`, `changeBIOMAPSDates`, `update_inprogressBIOMAPS`, `uploadBIOMAPSDashboardData`) should each have an API Gateway trigger configured.
- Lambda execution roles need:
  - `s3:GetObject` and `s3:PutObject` permissions on the in-progress and dashboard buckets.
  - Outbound HTTPS access to Qualtrics APIs.

---

## Typical Survey Lifecycle

```
1. Instructor fills out CIS in Qualtrics
                │
2. createBIOMAPSSurvey ──► New survey created + activated in Qualtrics
                │
3. update_inprogressBIOMAPS ──► Class added to in-progress tracking
                │
4. Instructor distributes survey link to students
                │
5. Students complete the assessment
                │
    ┌───────────────────────────────────────────┐
    │  automateBIOMAPS (scheduled, recurring)   │
    │                                           │
    │  • Checks each active class               │
    │  • Sends reminder if close date ≤ 4 days  │
    │  • Closes survey when date passes         │
    │  • Triggers data upload on close          │
    └───────────────────────────────────────────┘
                │
6. uploadBIOMAPSDashboardData ──► Scores + uploads processed data to S3
                │
7. Streamlit dashboard reads from S3 and displays results
```

If an instructor needs to reopen or extend their survey, they use **changeBIOMAPSDates**, which reactivates the survey, sets a new close date, and re-adds the class to in-progress tracking so `automateBIOMAPS` picks it up again.

---

## Troubleshooting

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| Survey not being monitored by automation | Class ID missing from in-progress CSV | Call `update_inprogressBIOMAPS` to add it |
| Reminder emails not sending | Reminder field set to "No" in CIS response, or close date is more than 4 days away | Use `changeBIOMAPSDates` to update reminder preference |
| Survey not closing automatically | Class ID not in in-progress CSV, or `automateBIOMAPS` schedule is paused | Verify EventBridge rule is active and class is tracked |
| Dashboard data not appearing | `uploadBIOMAPSDashboardData` failed or hasn't run yet | Check Lambda logs; may need to invoke manually |
| Duplicate data in dashboard | Survey was reopened and re-closed | The upload function handles this by removing existing rows with the same Class_ID before appending |
| 401 errors on API calls | `EXPECTED_TOKEN` mismatch between caller and Lambda | Verify environment variables match across all functions |
| Qualtrics API errors | Token expired or rate-limited | Verify `QUALTRICS_API_TOKEN` is current; check Qualtrics API limits |
