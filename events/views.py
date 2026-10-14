from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST

# Reuse the role_required decorator defined in Phase 1.
from accounts.views import role_required
from accounts.models import User

from .models import Event, Registration
from .forms import EventForm


# ===========================================================================
# ORGANIZER VIEWS
# ===========================================================================

# ---------------------------------------------------------------------------
# Organizer Event List  —  /events/
# ---------------------------------------------------------------------------

@role_required(User.ORGANIZER)
def event_list(request):
    """Show all events owned by the logged-in organizer."""
    events = Event.objects.filter(organizer=request.user)
    return render(request, 'events/event_list.html', {'events': events})


# ---------------------------------------------------------------------------
# Create Event  —  /events/create/
# ---------------------------------------------------------------------------

@role_required(User.ORGANIZER)
@require_http_methods(['GET', 'POST'])
def event_create(request):
    """Create a new event for the logged-in organizer."""
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            # Server-side assignment — never trust client input for these.
            event.organizer = request.user
            event.department = request.user.department
            event.status = Event.DRAFT
            event.save()
            messages.success(request, f'Event "{event.title}" created successfully!')
            return redirect('event_detail', pk=event.pk)
    else:
        form = EventForm()

    return render(request, 'events/event_form.html', {
        'form': form,
        'page_title': 'Create New Event',
        'submit_label': 'Create Event',
    })


# ---------------------------------------------------------------------------
# Event Detail  —  /events/<pk>/
# ---------------------------------------------------------------------------

@role_required(User.ORGANIZER)
def event_detail(request, pk):
    """Show details for one event. Only the owning organizer may view it."""
    event = get_object_or_404(Event, pk=pk)
    if event.organizer != request.user:
        return render(request, '403.html', status=403)
    return render(request, 'events/event_detail.html', {'event': event})


# ---------------------------------------------------------------------------
# Edit Event  —  /events/<pk>/edit/
# ---------------------------------------------------------------------------

@role_required(User.ORGANIZER)
@require_http_methods(['GET', 'POST'])
def event_edit(request, pk):
    """Edit a draft event. Non-draft events and other organizers' events are blocked."""
    event = get_object_or_404(Event, pk=pk)

    if event.organizer != request.user:
        return render(request, '403.html', status=403)

    if not event.is_draft():
        messages.warning(
            request,
            f'"{event.title}" cannot be edited because it is no longer a draft '
            f'(current status: {event.get_status_display()}).'
        )
        return redirect('event_detail', pk=event.pk)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            updated = form.save(commit=False)
            # Re-assert server-controlled fields so POST manipulation is ignored.
            updated.organizer = event.organizer
            updated.department = event.department
            updated.status = event.status
            updated.save()
            messages.success(request, f'Event "{updated.title}" updated successfully!')
            return redirect('event_detail', pk=updated.pk)
    else:
        form = EventForm(instance=event)

    return render(request, 'events/event_form.html', {
        'form': form,
        'event': event,
        'page_title': f'Edit Event — {event.title}',
        'submit_label': 'Save Changes',
    })


# ---------------------------------------------------------------------------
# Delete Event  —  /events/<pk>/delete/
# ---------------------------------------------------------------------------

@role_required(User.ORGANIZER)
def event_delete(request, pk):
    """
    Confirmation page (GET) and deletion (POST) for a draft event.
    Non-draft events and other organizers' events are blocked.
    """
    event = get_object_or_404(Event, pk=pk)

    if event.organizer != request.user:
        return render(request, '403.html', status=403)

    if not event.is_draft():
        messages.warning(
            request,
            f'"{event.title}" cannot be deleted because it is no longer a draft.'
        )
        return redirect('event_detail', pk=event.pk)

    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f'Event "{title}" deleted successfully.')
        return redirect('event_list')

    return render(request, 'events/event_confirm_delete.html', {'event': event})


# ===========================================================================
# HOD VIEWS  —  department-specific review
# ===========================================================================

def _same_department(user, event):
    """
    True only if the user has a department AND it matches the event's
    department (ignoring upper/lower case and extra spaces).
    A HOD with a blank department matches nothing.
    """
    user_dept = user.department.strip().lower()
    return bool(user_dept) and event.department.strip().lower() == user_dept


def _hod_event_or_denied(request, pk):
    """
    Load an event for HOD review.
    - Draft events are hidden from HODs completely (404).
    - Events from another department give a 403 page.
    Returns (event, None) on success or (event, 403_response) when denied.
    """
    event = get_object_or_404(Event.objects.exclude(status=Event.DRAFT), pk=pk)
    if not _same_department(request.user, event):
        return event, render(request, '403.html', status=403)
    return event, None


# ---------------------------------------------------------------------------
# HOD Review List  —  /events/review/
# ---------------------------------------------------------------------------

@role_required(User.HOD)
def hod_event_list(request):
    """Pending events from the HOD's own department, plus reviewed history."""
    dept = request.user.department.strip()
    if dept:
        pending_events = Event.objects.filter(
            status=Event.PENDING, department__iexact=dept
        ).order_by('date')
        reviewed_events = Event.objects.filter(
            status__in=[Event.APPROVED, Event.REJECTED], department__iexact=dept
        ).order_by('-updated_at')
    else:
        pending_events = Event.objects.none()
        reviewed_events = Event.objects.none()

    return render(request, 'events/hod_event_list.html', {
        'events': pending_events,
        'reviewed_events': reviewed_events,
    })


# ---------------------------------------------------------------------------
# HOD Event Detail  —  /events/review/<pk>/
# ---------------------------------------------------------------------------

@role_required(User.HOD)
def hod_event_detail(request, pk):
    """Show one non-draft event from the HOD's department."""
    event, denied = _hod_event_or_denied(request, pk)
    if denied:
        return denied
    return render(request, 'events/hod_event_detail.html', {'event': event})


# ---------------------------------------------------------------------------
# HOD Approve / Reject  —  POST only
# ---------------------------------------------------------------------------

@role_required(User.HOD)
@require_POST
def hod_event_approve(request, pk):
    """Approve a pending event in the HOD's department."""
    event, denied = _hod_event_or_denied(request, pk)
    if denied:
        return denied

    if event.status != Event.PENDING:
        messages.warning(
            request,
            f'"{event.title}" is not pending (current status: '
            f'{event.get_status_display()}), so it cannot be approved.'
        )
        return redirect('hod_event_detail', pk=event.pk)

    event.status = Event.APPROVED
    event.rejection_reason = ''  # clear any previous rejection reason
    event.save(update_fields=['status', 'rejection_reason', 'updated_at'])
    messages.success(request, f'Event "{event.title}" has been approved.')
    return redirect('hod_event_list')


@role_required(User.HOD)
@require_POST
def hod_event_reject(request, pk):
    """Reject a pending event; requires a non-empty reason."""
    event, denied = _hod_event_or_denied(request, pk)
    if denied:
        return denied

    if event.status != Event.PENDING:
        messages.warning(
            request,
            f'"{event.title}" is not pending (current status: '
            f'{event.get_status_display()}), so it cannot be rejected.'
        )
        return redirect('hod_event_detail', pk=event.pk)

    reason = request.POST.get('rejection_reason', '').strip()
    if not reason:
        messages.error(request, 'Please provide a rejection reason before rejecting.')
        return redirect('hod_event_detail', pk=event.pk)

    event.status = Event.REJECTED
    event.rejection_reason = reason
    event.save(update_fields=['status', 'rejection_reason', 'updated_at'])
    messages.success(request, f'Event "{event.title}" has been rejected.')
    return redirect('hod_event_list')


# ===========================================================================
# STUDENT VIEWS  —  browse approved events
# ===========================================================================

# ---------------------------------------------------------------------------
# Student Event List  —  /events/browse/
# ---------------------------------------------------------------------------

@role_required(User.PARTICIPANT)
def student_event_list(request):
    """List only APPROVED events, soonest first."""
    events = Event.objects.filter(status=Event.APPROVED).order_by('date')
    return render(request, 'events/student_event_list.html', {'events': events})


# ---------------------------------------------------------------------------
# Student Event Detail  —  /events/browse/<pk>/
# ---------------------------------------------------------------------------

@role_required(User.PARTICIPANT)
def student_event_detail(request, pk):
    """
    Show one APPROVED event. Any other status gives a 404 so students
    cannot even tell that a draft/pending/rejected event exists.
    """
    event = get_object_or_404(Event, pk=pk, status=Event.APPROVED)
    already_registered = Registration.objects.filter(
        event=event, student=request.user
    ).exists()
    return render(request, 'events/student_event_detail.html', {
        'event': event,
        'already_registered': already_registered,
    })

# ---------------------------------------------------------------------------
# Submit Event for Approval  —  /events/<pk>/submit/   (POST only)
# ---------------------------------------------------------------------------

@role_required(User.ORGANIZER)
@require_POST
def event_submit(request, pk):
    """
    Move a DRAFT event to PENDING so the department HOD can review it.
    The new status is set here on the server; nothing is read from the request.
    """
    event = get_object_or_404(Event, pk=pk)

    if event.organizer != request.user:
        return render(request, '403.html', status=403)

    if not event.is_draft():
        messages.warning(
            request,
            f'"{event.title}" cannot be submitted because it is not a draft '
            f'(current status: {event.get_status_display()}).'
        )
        return redirect('event_detail', pk=event.pk)

    event.status = Event.PENDING
    event.save(update_fields=['status', 'updated_at'])
    messages.success(
        request,
        f'Event "{event.title}" has been submitted for HOD approval.'
    )
    return redirect('event_detail', pk=event.pk)