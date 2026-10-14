# Campus Club — Phase 1

A Django web application for college club and event management.

## Phase 1 Features

- Custom user model with three roles: **Event Organizer**, **Participant (Student)**, and **HOD**
- Secure student self-registration (always creates `PARTICIPANT` accounts)
- Admin-managed Organizer and HOD accounts via Django Admin
- Login / logout with role-based dashboard redirect
- Three role-specific dashboards (placeholder content for Phase 2)
- Server-side role enforcement (403 on unauthorized access)
- Full automated test suite (37 tests)

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Apply Migrations

```bash
python manage.py migrate
```

### 3. Create a Superuser (for Django Admin)

```bash
python manage.py createsuperuser
```

### 4. Run the Development Server

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000/** in your browser.

---

## URL Reference

| URL | Purpose |
|-----|---------|
| `/` | Redirects to login |
| `/accounts/login/` | Login page |
| `/accounts/register/` | Student self-registration |
| `/accounts/logout/` | Logout (POST) |
| `/dashboard/` | Role-based redirect |
| `/dashboard/organizer/` | Organizer dashboard |
| `/dashboard/participant/` | Participant dashboard |
| `/dashboard/hod/` | HOD dashboard |
| `/admin/` | Django Admin |

---

## Creating Organizer / HOD Accounts

Organizer and HOD accounts **cannot** be self-registered. Use Django Admin:

1. Go to `http://127.0.0.1:8000/admin/`
2. Log in with your superuser credentials.
3. Click **Users → Add User**.
4. Fill in username and password, then set **Role** and **Department**.

---

## Running Tests

```bash
python manage.py test accounts --verbosity=2
```

Expected output: **37 tests, 0 failures, 0 errors.**

---

## Project Structure

```
campus_club/
├── manage.py
├── requirements.txt
├── .gitignore
├── README.md
├── campus_club/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── accounts/
│   ├── migrations/
│   ├── models.py        ← Custom User model
│   ├── forms.py         ← StudentRegistrationForm
│   ├── views.py         ← Auth views + dashboards
│   ├── urls.py          ← /accounts/* routes
│   ├── dashboard_urls.py← /dashboard/* routes
│   ├── admin.py         ← Extended UserAdmin
│   └── tests.py         ← 37 automated tests
├── templates/
│   ├── base.html
│   ├── 403.html
│   ├── accounts/
│   │   ├── login.html
│   │   ├── register.html
│   │   └── dashboard.html
│   └── registration/
│       └── logged_out.html
└── static/
    └── css/
        └── style.css
```

---

## Security Notes

- Public registration always assigns the `PARTICIPANT` role on the server — the form does not expose a role field, and the `save()` method forcibly sets `role = PARTICIPANT` regardless of POST data.
- Dashboard views use a `role_required` decorator that returns HTTP 403 for wrong-role access.
- All forms use Django's CSRF protection.
- Passwords are hashed using Django's default PBKDF2 algorithm.
- The `SECRET_KEY` should be set via the `DJANGO_SECRET_KEY` environment variable in production.

---

## Phase 2 (Not Yet Implemented)

- Event CRUD (Organizer)
- HOD event approval workflow
- Student event browsing and registration
- Attendance tracking
