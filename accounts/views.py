from functools import wraps
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .forms import StudentRegistrationForm
from .models import User


# ---------------------------------------------------------------------------
# Role-based access control decorators
# ---------------------------------------------------------------------------

def role_required(required_role):
    """
    Decorator that restricts a view to authenticated users with a specific role.
    - Unauthenticated users are redirected to the login page.
    - Authenticated users with the wrong role receive a 403 Forbidden page.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url='/accounts/login/')
        def _wrapped_view(request, *args, **kwargs):
            if request.user.role != required_role:
                return render(request, '403.html', status=403)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


# ---------------------------------------------------------------------------
# Authentication views
# ---------------------------------------------------------------------------

@require_http_methods(['GET', 'POST'])
def login_view(request):
    """Login view. Redirects authenticated users to the dashboard."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard_redirect')
        else:
            messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'accounts/login.html')


@require_http_methods(['GET', 'POST'])
def register_view(request):
    """
    Public student registration.
    Already-authenticated users are redirected away.
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f'Account created successfully! Welcome, {user.username}. Please log in.'
            )
            return redirect('login')
    else:
        form = StudentRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@require_http_methods(['POST'])
def logout_view(request):
    """Logout via POST only (CSRF-protected)."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


# ---------------------------------------------------------------------------
# Dashboard redirect — sends user to their role-specific dashboard
# ---------------------------------------------------------------------------

@login_required(login_url='/accounts/login/')
def dashboard_redirect(request):
    """Redirect the authenticated user to their role-specific dashboard."""
    role = request.user.role
    if role == User.ORGANIZER:
        return redirect('organizer_dashboard')
    elif role == User.HOD:
        return redirect('hod_dashboard')
    else:
        return redirect('participant_dashboard')


# ---------------------------------------------------------------------------
# Role-specific dashboards
# ---------------------------------------------------------------------------

@role_required(User.ORGANIZER)
def organizer_dashboard(request):
    # Import here to avoid circular imports with the events app.
    from events.models import Event
    total_events = Event.objects.filter(organizer=request.user).count()
    draft_events = Event.objects.filter(organizer=request.user, status=Event.DRAFT).count()
    return render(request, 'accounts/dashboard.html', {
        'dashboard_title': 'Event Organizer Dashboard',
        'role_label': 'Event Organizer',
        'total_events': total_events,
        'draft_events': draft_events,
    })


@role_required(User.PARTICIPANT)
def participant_dashboard(request):
    return render(request, 'accounts/dashboard.html', {
        'dashboard_title': 'Student Dashboard',
        'role_label': 'Participant (Student)',
        'placeholder_text': (
            'Event browsing and registration will be implemented in Phase 2.'
        ),
    })


@role_required(User.HOD)
def hod_dashboard(request):
    # Import here to avoid circular imports with the events app.
    from events.models import Event
    dept = request.user.department.strip()
    if dept:
        pending_count = Event.objects.filter(
            status=Event.PENDING, department__iexact=dept
        ).count()
    else:
        pending_count = 0
    return render(request, 'accounts/dashboard.html', {
        'dashboard_title': 'HOD Dashboard',
        'role_label': 'Head of Department (HOD)',
        'pending_count': pending_count,
    })