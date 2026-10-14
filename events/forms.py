from decimal import Decimal  # noqa: F401  (kept for clarity)

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import (
    Event,
    Registration,
    RegistrationAnswer,
    RegistrationField,
)


class EventForm(forms.ModelForm):
    """
    ModelForm for creating and editing events.

    Exposes only the fields that organizers are allowed to supply:
        title, description, date, venue.

    organizer, department, and status are set exclusively on the server
    — they are intentionally excluded from this form.
    """

    class Meta:
        model = Event
        fields = ('title', 'description', 'date', 'venue')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Event title',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the event…',
            }),
            # HTML5 datetime-local input for a good UX
            'date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }, format='%Y-%m-%dT%H:%M'),
            'venue': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Main Auditorium, Room 201',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Render the date field in the format the datetime-local widget expects.
        self.fields['date'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']

    def clean_date(self):
        event_date = self.cleaned_data.get('date')
        if event_date and event_date < timezone.now():
            raise forms.ValidationError('The event date cannot be in the past.')
        return event_date


# ---------------------------------------------------------------------------
# Organizer: add / edit one custom question
# ---------------------------------------------------------------------------

class RegistrationFieldForm(forms.ModelForm):
    """
    One custom question. The event is set by the view, never by the browser.
    """

    class Meta:
        model = RegistrationField
        fields = ('label', 'field_type', 'required', 'options', 'order')
        labels = {
            'label': 'Question',
            'field_type': 'Answer type',
            'required': 'Required',
            'options': 'Dropdown options',
            'order': 'Display order',
        }
        help_texts = {
            'options': 'Only for the Dropdown type. Enter one option per line (at least two).',
            'order': 'Smaller numbers appear first.',
        }
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Why do you want to join?',
            }),
            'field_type': forms.Select(attrs={'class': 'form-select'}),
            'required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'options': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Option 1\nOption 2\nOption 3',
            }),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        field_type = cleaned.get('field_type')
        options = cleaned.get('options', '')

        if field_type == RegistrationField.SELECT:
            lines = [line.strip() for line in options.splitlines() if line.strip()]
            if len(lines) < 2:
                self.add_error('options', 'A dropdown needs at least two options, one per line.')
            elif len({line.lower() for line in lines}) != len(lines):
                self.add_error('options', 'Dropdown options must be different from each other.')
            elif any(len(line) > 200 for line in lines):
                self.add_error('options', 'Each option must be 200 characters or fewer.')
            else:
                cleaned['options'] = '\n'.join(lines)
        elif field_type:
            # Options only make sense for dropdowns.
            cleaned['options'] = ''

        return cleaned


# ---------------------------------------------------------------------------
# Student: the application form (built from the event's questions)
# ---------------------------------------------------------------------------

class RegistrationApplicationForm(forms.Form):
    """
    Dynamic form for one event.

    - Name, email and department come from the logged-in account.
    - Roll number is asked only if the account does not have one yet.
    - Each custom question becomes a field named question_<id>.
    - The student is NEVER read from submitted data.
    """

    full_name = forms.CharField(
        max_length=150,
        label='Full Name',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Ravi Kumar',
        }),
    )

    roll_number = forms.CharField(
        max_length=30,
        label='Roll Number',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 21CS001',
        }),
    )

    def __init__(self, *args, event, student, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.student = student
        self.questions = list(event.registration_fields.all())

        # Full name already set? Show it as read-only, not editable.
        if student.first_name or student.last_name:
            del self.fields['full_name']

        # Roll number already on the account? Then it is fixed and not editable.
        if student.roll_number:
            del self.fields['roll_number']

        for question in self.questions:
            self.fields[self.field_name(question)] = self._build_field(question)

    @staticmethod
    def field_name(question):
        return f'question_{question.pk}'

    def _build_field(self, q):
        required = q.required
        label = q.label

        if q.field_type == RegistrationField.TEXTAREA:
            return forms.CharField(
                label=label, required=required, max_length=2000,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            )
        if q.field_type == RegistrationField.NUMBER:
            return forms.DecimalField(
                label=label, required=required, max_digits=15, decimal_places=4,
                widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            )
        if q.field_type == RegistrationField.SELECT:
            choices = [('', '— Select —')] + [(o, o) for o in q.option_list()]
            return forms.ChoiceField(
                label=label, required=required, choices=choices,
                widget=forms.Select(attrs={'class': 'form-select'}),
            )
        if q.field_type == RegistrationField.CHECKBOX:
            return forms.BooleanField(
                label=label, required=required,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            )
        # Default: short text
        return forms.CharField(
            label=label, required=required, max_length=255,
            widget=forms.TextInput(attrs={'class': 'form-control'}),
        )

    def clean_roll_number(self):
        value = self.cleaned_data['roll_number'].strip()
        User = get_user_model()
        clash = (
            User.objects.filter(roll_number__iexact=value)
            .exclude(pk=self.student.pk)
            .exists()
        )
        if clash:
            raise forms.ValidationError(
                'This roll number is already linked to another account.'
            )
        return value

    def _answer_text(self, question):
        value = self.cleaned_data.get(self.field_name(question))
        if question.field_type == RegistrationField.CHECKBOX:
            return 'Yes' if value else 'No'
        if question.field_type == RegistrationField.NUMBER:
            return '' if value is None else format(value.normalize(), 'f')
        return (value or '').strip()

    @transaction.atomic
    def save(self):
        """
        Create the Registration and all its answers in one transaction.
        If anything fails, nothing is saved.
        """
        # Save full name if it was provided (first registration).
        if 'full_name' in self.cleaned_data:
            full = self.cleaned_data['full_name'].strip()
            parts = full.split(' ', 1)
            self.student.first_name = parts[0]
            self.student.last_name = parts[1] if len(parts) > 1 else ''
            self.student.save(update_fields=['first_name', 'last_name'])

        if 'roll_number' in self.cleaned_data:
            self.student.roll_number = self.cleaned_data['roll_number']
            self.student.save(update_fields=['roll_number'])

        registration = Registration.objects.create(
            event=self.event,
            student=self.student,
        )
        for question in self.questions:
            RegistrationAnswer.objects.create(
                registration=registration,
                field=question,
                answer=self._answer_text(question),
            )
        return registration