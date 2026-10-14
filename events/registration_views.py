from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.views import role_required
from accounts.models import User

from .forms import RegistrationFieldForm, RegistrationApplicationForm
from .models import Event, Registration, RegistrationField


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _owned_event(request, pk):
    """Return (event, None) if the organizer owns it, else (event, 403 response)."""
    event = get_object_or_404(Event, pk=pk)
    if event.organizer != request.user:
        return event, render(request, '403.html', status=403)
    return event, None


def _form_lock_state(event):
    """
    Return (can_edit, reason).
    The form can be changed only for DRAFT/REJECTED events with no registrations.
    """
    if event.status not in (Event.DRAFT, Event.REJECTED):
        return False, (
            'The registration form can only be changed while the event is a draft '
            f'or rejected (current status: {event.get_status_display()}).'
        )
    if event.registrations.exists():
        return False, (
            'This form can no longer be modified because students have '
            'already registered.'
        )
    return True, ''


# ===========================================================================
# ORGANIZER: form builder
# ===========================================================================

@role_required(User.ORGANIZER)
@require_http_methods(['GET', 'POST'])
def form_builder(request, pk):
    """List the event's custom questions and add a new one."""
    event, denied = _owned_event(request, pk)
    if denied:
        return denied

    can_edit, lock_reason = _form_lock_state(event)

    if request.method == 'POST':
        if not can_edit:
            messages.warning(request, lock_reason)
            return redirect('form_builder', pk=event.pk)
        form = RegistrationFieldForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.event = event          # server-side, never from the browser
            question.save()
            messages.success(request, f'Question "{question.label}" added.')
            return redirect('form_builder', pk=event.pk)
    else:
        form = RegistrationFieldForm(
            initial={'order': event.registration_fields.count() + 1}
        )

    return render(request, 'events/form_builder.html', {
        'event': event,
        'questions': event.registration_fields.all(),
        'form': form,
        'can_edit': can_edit,
        'lock_reason': lock_reason,
    })


@role_required(User.ORGANIZER)
@require_http_methods(['GET', 'POST'])
def form_field_edit(request, pk, field_pk):
    event, denied = _owned_event(request, pk)
    if denied:
        return denied

    # Looking the question up through THIS event stops cross-event editing.
    question = get_object_or_404(RegistrationField, pk=field_pk, event=event)

    can_edit, lock_reason = _form_lock_state(event)
    if not can_edit:
        messages.warning(request, lock_reason)
        return redirect('form_builder', pk=event.pk)

    if request.method == 'POST':
        form = RegistrationFieldForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, f'Question "{question.label}" updated.')
            return redirect('form_builder', pk=event.pk)
    else:
        form = RegistrationFieldForm(instance=question)

    return render(request, 'events/form_field_edit.html', {
        'event': event,
        'question': question,
        'form': form,
    })


@role_required(User.ORGANIZER)
@require_POST
def form_field_delete(request, pk, field_pk):
    event, denied = _owned_event(request, pk)
    if denied:
        return denied

    question = get_object_or_404(RegistrationField, pk=field_pk, event=event)

    can_edit, lock_reason = _form_lock_state(event)
    if not can_edit:
        messages.warning(request, lock_reason)
        return redirect('form_builder', pk=event.pk)

    label = question.label
    question.delete()
    messages.success(request, f'Question "{label}" removed.')
    return redirect('form_builder', pk=event.pk)


# ===========================================================================
# ORGANIZER: applicants
# ===========================================================================

@role_required(User.ORGANIZER)
def applicant_list(request, pk):
    event, denied = _owned_event(request, pk)
    if denied:
        return denied

    questions = list(event.registration_fields.all())
    registrations = (
        event.registrations
        .select_related('student')
        .prefetch_related('answers')
    )

    rows = []
    for registration in registrations:
        answer_by_field = {a.field_id: a.answer for a in registration.answers.all()}
        rows.append({
            'registration': registration,
            # Same order as the question headers in the table.
            'answers': [answer_by_field.get(q.pk, '') for q in questions],
        })

    return render(request, 'events/applicant_list.html', {
        'event': event,
        'questions': questions,
        'rows': rows,
        'applicant_count': len(rows),
    })


@role_required(User.ORGANIZER)
def applicant_detail(request, pk, registration_pk):
    event, denied = _owned_event(request, pk)
    if denied:
        return denied

    # Looked up through THIS event, so a guessed ID from another event gives 404.
    registration = get_object_or_404(
        Registration.objects.select_related('student'),
        pk=registration_pk,
        event=event,
    )
    answer_by_field = {a.field_id: a.answer for a in registration.answers.all()}
    qa_pairs = [
        (q, answer_by_field.get(q.pk, ''))
        for q in event.registration_fields.all()
    ]
    return render(request, 'events/applicant_detail.html', {
        'event': event,
        'registration': registration,
        'qa_pairs': qa_pairs,
    })


# ===========================================================================
# STUDENT: apply, my registrations
# ===========================================================================

@role_required(User.PARTICIPANT)
@require_http_methods(['GET', 'POST'])
def event_register(request, pk):
    """Application form for an APPROVED event. Student comes from request.user."""
    event = get_object_or_404(Event, pk=pk, status=Event.APPROVED)

    if Registration.objects.filter(event=event, student=request.user).exists():
        messages.info(request, 'You have already registered for this event.')
        return redirect('student_event_detail', pk=event.pk)

    if request.method == 'POST':
        form = RegistrationApplicationForm(
            request.POST, event=event, student=request.user
        )
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                # Two quick submissions: the database constraint caught the second.
                messages.info(request, 'You have already registered for this event.')
                return redirect('student_event_detail', pk=event.pk)
            messages.success(
                request, f'You have registered for "{event.title}".'
            )
            return redirect('my_registrations')
    else:
        form = RegistrationApplicationForm(event=event, student=request.user)

    return render(request, 'events/registration_form.html', {
        'event': event,
        'form': form,
    })


@role_required(User.PARTICIPANT)
def my_registrations(request):
    registrations = (
        Registration.objects
        .filter(student=request.user)
        .select_related('event')
    )
    return render(request, 'registrations/my_registrations.html', {
        'registrations': registrations,
    })


@role_required(User.PARTICIPANT)
def registration_detail(request, pk):
    # Filtering by student=request.user means other students' IDs give 404.
    registration = get_object_or_404(
        Registration.objects.select_related('event'),
        pk=pk,
        student=request.user,
    )
    answer_by_field = {a.field_id: a.answer for a in registration.answers.all()}
    qa_pairs = [
        (q, answer_by_field.get(q.pk, ''))
        for q in registration.event.registration_fields.all()
    ]
    return render(request, 'registrations/registration_detail.html', {
        'registration': registration,
        'qa_pairs': qa_pairs,
    })

# ===========================================================================
# ORGANIZER: attendance
# ===========================================================================

ATTENDANCE_EVENT_STATUSES = (Event.APPROVED, Event.COMPLETED)


def _attendance_unavailable(request, event):
    """
    Attendance only works for approved or completed events.
    Returns a redirect response when it is not allowed, otherwise None.
    """
    if event.status not in ATTENDANCE_EVENT_STATUSES:
        messages.warning(
            request,
            'Attendance is only available for approved or completed events '
            f'(current status: {event.get_status_display()}).'
        )
        return redirect('event_detail', pk=event.pk)
    return None


@role_required(User.ORGANIZER)
def attendance(request, pk):
    """Attendance sheet for one event: counts, filter, and Present/Absent buttons."""
    event, denied = _owned_event(request, pk)
    if denied:
        return denied

    unavailable = _attendance_unavailable(request, event)
    if unavailable:
        return unavailable

    all_registrations = event.registrations.all()
    counts = all_registrations.aggregate(
        total=Count('pk'),
        present=Count('pk', filter=Q(attendance_status=Registration.PRESENT)),
        absent=Count('pk', filter=Q(attendance_status=Registration.ABSENT)),
        not_marked=Count('pk', filter=Q(attendance_status=Registration.NOT_MARKED)),
    )

    show_unmarked = request.GET.get('filter') == 'unmarked'
    registrations = all_registrations.select_related('student', 'attendance_marked_by')
    if show_unmarked:
        registrations = registrations.filter(attendance_status=Registration.NOT_MARKED)
    registrations = registrations.order_by('student__roll_number', 'student__username')

    return render(request, 'events/attendance.html', {
        'event': event,
        'registrations': registrations,
        'counts': counts,
        'show_unmarked': show_unmarked,
    })


@role_required(User.ORGANIZER)
@require_POST
def attendance_mark(request, pk, registration_pk):
    """Mark one registration Present or Absent (POST only). Can be corrected later."""
    event, denied = _owned_event(request, pk)
    if denied:
        return denied

    unavailable = _attendance_unavailable(request, event)
    if unavailable:
        return unavailable

    # Looked up through THIS event, so a registration from another event gives 404.
    registration = get_object_or_404(
        Registration.objects.select_related('student'),
        pk=registration_pk,
        event=event,
    )

    back = reverse('attendance', args=[event.pk])
    if request.POST.get('filter') == 'unmarked':
        back += '?filter=unmarked'

    status = request.POST.get('status')
    if status not in (Registration.PRESENT, Registration.ABSENT):
        messages.error(request, 'Invalid attendance value. Nothing was changed.')
        return redirect(back)

    # Everything below is decided by the server, not the browser.
    registration.attendance_status = status
    registration.attendance_marked_at = timezone.now()
    registration.attendance_marked_by = request.user
    registration.save(update_fields=[
        'attendance_status', 'attendance_marked_at', 'attendance_marked_by',
    ])

    name = registration.student.get_full_name() or registration.student.username
    messages.success(
        request,
        f'{name} marked {registration.get_attendance_status_display().lower()}.'
    )
    return redirect(back)