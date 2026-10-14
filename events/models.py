from django.conf import settings
from django.db import models
from django.utils import timezone


class Event(models.Model):
    """
    Represents a campus club event created by an organizer.

    Status flow (Phase 2 implements DRAFT only; other statuses exist for
    future phases):
        DRAFT → PENDING → APPROVED / REJECTED → COMPLETED
    """

    DRAFT = 'draft'
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    COMPLETED = 'completed'

    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (PENDING, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (COMPLETED, 'Completed'),
    ]

    # Status badge colours used in templates
    STATUS_BADGE = {
        DRAFT: 'secondary',
        PENDING: 'warning',
        APPROVED: 'success',
        REJECTED: 'danger',
        COMPLETED: 'primary',
    }

    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateTimeField(help_text='Date and time of the event.')
    venue = models.CharField(max_length=200)

    # Organizer is always set server-side from request.user.
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='events',
    )

    # Copied from organizer.department at creation time.
    department = models.CharField(max_length=100, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
    )

    # Set by the HOD when an event is rejected; cleared on approval.
    rejection_reason = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Event'
        verbose_name_plural = 'Events'

    def __str__(self):
        return f'{self.title} [{self.get_status_display()}]'

    def is_draft(self):
        return self.status == self.DRAFT

    def badge_colour(self):
        return self.STATUS_BADGE.get(self.status, 'secondary')

# ===========================================================================
# Registration models
# ===========================================================================

class Registration(models.Model):
    """A student's application to an event. One per (event, student)."""

    NOT_MARKED = 'not_marked'
    PRESENT = 'present'
    ABSENT = 'absent'

    ATTENDANCE_CHOICES = [
        (NOT_MARKED, 'Not Marked'),
        (PRESENT, 'Present'),
        (ABSENT, 'Absent'),
    ]

    ATTENDANCE_BADGE = {
        NOT_MARKED: 'secondary',
        PRESENT: 'success',
        ABSENT: 'danger',
    }

    # PROTECT keeps application history safe: an event or student that has
    # registrations cannot be deleted by accident.
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name='registrations',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='registrations',
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    # Attendance (set only by the owning organizer, never by the student)
    attendance_status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_CHOICES,
        default=NOT_MARKED,
    )
    attendance_marked_at = models.DateTimeField(null=True, blank=True)
    attendance_marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='attendance_marked',
    )

    class Meta:
        ordering = ['-applied_at']
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'student'],
                name='unique_registration_per_event_student',
            ),
        ]

    def __str__(self):
        return f'{self.student} -> {self.event.title}'

    def attendance_badge(self):
        return self.ATTENDANCE_BADGE.get(self.attendance_status, 'secondary')


class RegistrationField(models.Model):
    """One custom question the organizer adds to an event's form."""

    TEXT = 'text'
    TEXTAREA = 'textarea'
    NUMBER = 'number'
    SELECT = 'select'
    CHECKBOX = 'checkbox'

    FIELD_TYPE_CHOICES = [
        (TEXT, 'Short text'),
        (TEXTAREA, 'Long text'),
        (NUMBER, 'Number'),
        (SELECT, 'Dropdown'),
        (CHECKBOX, 'Checkbox'),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='registration_fields',
    )
    label = models.CharField(max_length=200)
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPE_CHOICES,
        default=TEXT,
    )
    required = models.BooleanField(default=False)
    options = models.TextField(
        blank=True,
        help_text='Dropdown choices, one per line.',
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.label} ({self.get_field_type_display()})'

    def option_list(self):
        """Dropdown options as a clean list (blank lines removed)."""
        return [line.strip() for line in self.options.splitlines() if line.strip()]


class RegistrationAnswer(models.Model):
    """A student's answer to one custom question."""

    registration = models.ForeignKey(
        Registration,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    # PROTECT: a question that has answers cannot be deleted.
    field = models.ForeignKey(
        RegistrationField,
        on_delete=models.PROTECT,
        related_name='answers',
    )
    answer = models.TextField(blank=True, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['registration', 'field'],
                name='unique_answer_per_registration_field',
            ),
        ]

    def __str__(self):
        return f'{self.field.label}: {self.answer[:30]}'