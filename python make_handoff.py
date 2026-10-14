from pathlib import Path
import zipfile

root = Path.cwd()
output = root / "campus_club_handoff.zip"

include_files = [
    "manage.py",
    "README.md",
    "requirements.txt",
    ".gitignore",
    "campus_club/settings.py",
    "campus_club/urls.py",
    "accounts/models.py",
    "accounts/forms.py",
    "accounts/views.py",
    "accounts/urls.py",
    "accounts/dashboard_urls.py",
    "accounts/admin.py",
    "accounts/tests.py",
    "accounts/migrations/0001_initial.py",
    "events/models.py",
    "events/forms.py",
    "events/views.py",
    "events/urls.py",
    "events/admin.py",
    "events/tests.py",
    "events/migrations/0001_initial.py",
    "templates/base.html",
    "templates/403.html",
    "templates/accounts/dashboard.html",
    "templates/accounts/login.html",
    "templates/accounts/register.html",
    "templates/events/event_list.html",
    "templates/events/event_detail.html",
    "templates/events/event_form.html",
    "templates/events/event_confirm_delete.html",
    "templates/registration/logged_out.html",
    "static/css/style.css",
]

with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for filename in include_files:
        path = root / filename

        if path.is_file():
            # Store only the filename, without its original directories
            archive.write(path, arcname=Path(filename).name)
        else:
            print(f"Missing, skipped: {filename}")

print(f"Created: {output}")
print(f"Size: {output.stat().st_size:,} bytes")