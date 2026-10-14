# Campus Club — College Event Management System

A Django-based web application for managing college events, student registrations, department-level event approvals, and attendance through a simple, role-based interface.

Campus Club provides a centralized platform where students can discover approved events and apply, organizers can create and manage events, and Heads of Department (HODs) can review events submitted for approval.

## Features

### 1. Authentication and Role-Based Access
- Student self-registration and login.
- Separate roles for **Participants, Organizers, and HODs**.
- Role-specific dashboards and navigation.
- Access restrictions for protected pages and actions.
- Organizer and HOD accounts managed by an administrator.
- Django admin integration for account management.

### 2. Event Management
- Create, view, and manage college events.
- Maintain event details such as title, description, date, venue, and department.
- Track event status through the approval workflow.
- Submit draft events for HOD approval.
- Restrict event reviews to the HOD responsible for the relevant department.
- Preserve submitted and approved event history rather than allowing unrestricted deletion.

**Event approval workflow:**

`Draft → Pending Approval → Approved / Rejected`

Students can browse approved events. Events that have not been approved are not available for student registration.

### 3. Custom Registration Forms
- Provide standard student information from the student's account.
- Allow organizers to configure additional questions for their events.
- Support short text, long text, number, dropdown, and checkbox question types.
- Configure required questions and dropdown options.
- Validate submitted answers on the server.
- Prevent duplicate applications to the same event.
- Restrict form management to the event's organizer.
- Lock registration forms when the event enters the submission workflow or registrations already exist, according to the application's rules.

### 4. Student Applications
- Apply to approved events.
- View personal registrations in **My Registrations**.
- Review submitted application details and custom answers.
- View registration and attendance information.
- Prevent students from viewing other students' private application details.

### 5. Organizer Applicant Management
- View applicants for events created by the organizer.
- Review student information and answers to custom questions.
- Keep applicant access restricted to the relevant event organizer.

### 6. Attendance Tracking
- View registered students for an event.
- Mark registered students as present or absent.
- Track attendance status for each registration.
- Display attendance information to students for their own applications.
- Review attendance counts for an event.
- Restrict attendance management to authorized organizers and events.

### 7. User Interface
- Bootstrap-based responsive layouts.
- Custom CSS in `static/css/style.css`.
- Modern cards, buttons, tables, forms, alerts, and status badges.
- Role-specific navigation and dashboards.
- Clear event status indicators and application empty states.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application programming language |
| Django | Web framework and server-side logic |
| SQLite | Development database |
| HTML5 | Page structure |
| CSS3 | Custom styling |
| Bootstrap 5 | Responsive layout and UI components |
| Bootstrap Icons | Interface icons |
| Django Templates | Dynamic server-rendered pages |

## Project Structure

```text
PBL/
├── manage.py
├── requirements.txt
├── README.md
├── .gitignore
├── campus_club/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── accounts/
│   ├── migrations/
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── dashboard_urls.py
│   ├── admin.py
│   └── tests.py
├── events/
│   ├── migrations/
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── tests.py
├── templates/
│   ├── base.html
│   ├── 403.html
│   ├── accounts/
│   ├── events/
│   ├── registrations/
│   └── registration/
└── static/
    └── css/
        └── style.css
```

*The exact files and template folders may vary slightly as the project evolves.*

## Installation and Setup

### Prerequisites

- Python 3.10 or newer, compatible with the Django version in `requirements.txt`.
- pip.
- Git, if cloning the project repository.

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd PBL
```

Replace the placeholder with your repository URL.

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / WSL:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Apply database migrations

```bash
python manage.py migrate
```

If you have modified Django models and new migrations have not yet been created, run:

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create an administrator account

```bash
python manage.py createsuperuser
```

Follow the prompts to create the account.

### 6. Start the development server

```bash
python manage.py runserver
```

Open the application at:

http://127.0.0.1:8000/

Access the Django administration interface at:

http://127.0.0.1:8000/admin/

## User Roles

| Role | Responsibilities |
|---|---|
| Participant | Register, browse approved events, apply, view personal registrations, and check attendance |
| Organizer | Create events, configure registration forms, submit events for approval, manage applicants, and track attendance |
| HOD | Review events belonging to the assigned department and approve or reject submissions |
| Administrator | Manage accounts and administrative configuration |

## Typical Workflow

1. An administrator creates organizer and HOD accounts and assigns departments.
2. A student creates a participant account.
3. An organizer creates an event and configures its registration questions.
4. The organizer submits the event for approval.
5. The relevant HOD reviews the event and approves or rejects it.
6. Students browse approved events and submit applications.
7. The organizer reviews applicants and their answers.
8. The organizer records attendance for registered students.
9. Students check their registration and attendance information.

## Running Tests

Run the Django test suite with:

```bash
python manage.py test
```

Check the project configuration with:

```bash
python manage.py check
```

These commands help identify test failures and configuration issues after code changes.

## Database and Development Notes

- SQLite is used for local development.
- Database migrations are maintained by Django.
- Do not commit secrets, environment files containing credentials, or local virtual environments.
- Keep `db.sqlite3` out of version control unless there is a specific, intentional reason to distribute a development database.
- Before deploying publicly, configure production settings, secret management, HTTPS, static files, and an appropriate production database.

## Project Goals

Campus Club aims to simplify college event administration by bringing event creation, departmental approval, student applications, and attendance tracking into one application.

The project also provides practical experience with Django models, forms, authentication, authorization, relational data, server-side validation, templates, and responsive web design.

## License

Add a license to this project if you intend to distribute or reuse it publicly. Until a license is specified, all rights remain with the copyright holder.

