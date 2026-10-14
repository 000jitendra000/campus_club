"""
Tests for registration forms, student applications, My Registrations and
organizer applicant lists.
"""

from datetime import timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .forms import RegistrationApplicationForm
from .models import Event, Registration, RegistrationAnswer, RegistrationField


def make_user(username, role, department='', roll_number=''):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='TestPass123!',
        role=role,
        department=department,
        roll_number=roll_number,
    )


def make_event(organizer, title='Event', status=Event.DRAFT):
    return Event.objects.create(
        title=title,
        description='Description',
        date=timezone.now() + timedelta(days=7),
        venue='Hall A',
        organizer=organizer,
        department=organizer.department,
        status=status,
    )


def make_question(event, label='Question', field_type=RegistrationField.TEXT,
                  required=False, options='', order=1):
    return RegistrationField.objects.create(
        event=event, label=label, field_type=field_type,
        required=required, options=options, order=order,
    )


def k(question):
    """POST key for a custom question."""
    return f'question_{question.pk}'


class Base(TestCase):
    def setUp(self):
        self.org = make_user('org1', User.ORGANIZER, 'CSE')
        self.other_org = make_user('org2', User.ORGANIZER, 'ECE')
        self.hod = make_user('hod1', User.HOD, 'CSE')
        self.student = make_user('stu1', User.PARTICIPANT, 'CSE', '21CS001')
        self.other_student = make_user('stu2', User.PARTICIPANT, 'ECE', '21EC002')
        self.draft = make_event(self.org, 'Draft Event')
        self.approved = make_event(self.org, 'Approved Event', Event.APPROVED)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RegistrationModelTests(Base):

    def test_registration_belongs_to_event_and_student(self):
        reg = Registration.objects.create(event=self.approved, student=self.student)
        self.assertEqual(reg.event, self.approved)
        self.assertEqual(reg.student, self.student)

    def test_duplicate_registration_prevented_by_database(self):
        Registration.objects.create(event=self.approved, student=self.student)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Registration.objects.create(event=self.approved, student=self.student)

    def test_answers_belong_to_registration_and_field(self):
        question = make_question(self.approved, 'Why?')
        reg = Registration.objects.create(event=self.approved, student=self.student)
        RegistrationAnswer.objects.create(registration=reg, field=question, answer='Fun')
        answer = reg.answers.get()
        self.assertEqual(answer.field, question)
        self.assertEqual(answer.answer, 'Fun')

    def test_duplicate_answer_prevented(self):
        question = make_question(self.approved)
        reg = Registration.objects.create(event=self.approved, student=self.student)
        RegistrationAnswer.objects.create(registration=reg, field=question, answer='A')
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistrationAnswer.objects.create(registration=reg, field=question, answer='B')


# ---------------------------------------------------------------------------
# Form builder
# ---------------------------------------------------------------------------

class FormBuilderTests(Base):

    def _add(self, event=None, **overrides):
        data = {
            'label': 'Why join?',
            'field_type': 'text',
            'required': 'on',
            'options': '',
            'order': 1,
        }
        data.update(overrides)
        event = event or self.draft
        return self.client.post(reverse('form_builder', args=[event.pk]), data)

    def test_owner_can_view_builder(self):
        self.client.force_login(self.org)
        response = self.client.get(reverse('form_builder', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 200)

    def test_owner_can_add_question_to_draft(self):
        self.client.force_login(self.org)
        self._add()
        question = RegistrationField.objects.get(event=self.draft)
        self.assertEqual(question.label, 'Why join?')
        self.assertTrue(question.required)

    def test_owner_can_add_question_to_rejected_event(self):
        rejected = make_event(self.org, 'Rejected', Event.REJECTED)
        self.client.force_login(self.org)
        self._add(event=rejected)
        self.assertEqual(rejected.registration_fields.count(), 1)

    def test_owner_can_edit_question(self):
        question = make_question(self.draft, 'Old label')
        self.client.force_login(self.org)
        self.client.post(
            reverse('form_field_edit', args=[self.draft.pk, question.pk]),
            {'label': 'New label', 'field_type': 'textarea', 'options': '', 'order': 2},
        )
        question.refresh_from_db()
        self.assertEqual(question.label, 'New label')
        self.assertEqual(question.field_type, 'textarea')
        self.assertFalse(question.required)

    def test_owner_can_delete_question_via_post(self):
        question = make_question(self.draft)
        self.client.force_login(self.org)
        self.client.post(reverse('form_field_delete', args=[self.draft.pk, question.pk]))
        self.assertFalse(RegistrationField.objects.filter(pk=question.pk).exists())

    def test_delete_requires_post(self):
        question = make_question(self.draft)
        self.client.force_login(self.org)
        response = self.client.get(reverse('form_field_delete', args=[self.draft.pk, question.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(RegistrationField.objects.filter(pk=question.pk).exists())

    def test_other_organizer_cannot_use_builder(self):
        question = make_question(self.draft)
        self.client.force_login(self.other_org)
        self.assertEqual(
            self.client.get(reverse('form_builder', args=[self.draft.pk])).status_code, 403)
        self.assertEqual(self._add().status_code, 403)
        self.assertEqual(self.client.post(
            reverse('form_field_edit', args=[self.draft.pk, question.pk]),
            {'label': 'Hacked', 'field_type': 'text', 'options': '', 'order': 1},
        ).status_code, 403)
        self.assertEqual(self.client.post(
            reverse('form_field_delete', args=[self.draft.pk, question.pk])).status_code, 403)
        question.refresh_from_db()
        self.assertNotEqual(question.label, 'Hacked')

    def test_participant_and_hod_cannot_use_builder(self):
        for user in (self.student, self.hod):
            self.client.force_login(user)
            response = self.client.get(reverse('form_builder', args=[self.draft.pk]))
            self.assertEqual(response.status_code, 403)
            self.assertEqual(self._add().status_code, 403)
        self.assertEqual(RegistrationField.objects.count(), 0)

    def test_anonymous_redirected(self):
        response = self.client.get(reverse('form_builder', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_field_cannot_be_edited_through_another_events_url(self):
        other_event = make_event(self.org, 'Other Draft')
        question = make_question(other_event, 'Belongs to other')
        self.client.force_login(self.org)
        url = reverse('form_field_edit', args=[self.draft.pk, question.pk])
        response = self.client.post(
            url, {'label': 'Changed', 'field_type': 'text', 'options': '', 'order': 1})
        self.assertEqual(response.status_code, 404)
        question.refresh_from_db()
        self.assertEqual(question.label, 'Belongs to other')

    def test_field_cannot_be_deleted_through_another_events_url(self):
        other_event = make_event(self.org, 'Other Draft')
        question = make_question(other_event)
        self.client.force_login(self.org)
        response = self.client.post(
            reverse('form_field_delete', args=[self.draft.pk, question.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(RegistrationField.objects.filter(pk=question.pk).exists())

    def test_invalid_field_type_rejected(self):
        self.client.force_login(self.org)
        response = self._add(field_type='file_upload')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RegistrationField.objects.count(), 0)

    def test_dropdown_requires_options(self):
        self.client.force_login(self.org)
        self._add(field_type='select', options='')
        self._add(field_type='select', options='Only one')
        self.assertEqual(RegistrationField.objects.count(), 0)

    def test_dropdown_rejects_duplicate_options(self):
        self.client.force_login(self.org)
        self._add(field_type='select', options='Red\nred')
        self.assertEqual(RegistrationField.objects.count(), 0)

    def test_dropdown_with_valid_options_saved(self):
        self.client.force_login(self.org)
        self._add(field_type='select', options='Red\n\n Blue \nGreen')
        question = RegistrationField.objects.get()
        self.assertEqual(question.option_list(), ['Red', 'Blue', 'Green'])

    def test_options_cleared_for_non_dropdown(self):
        self.client.force_login(self.org)
        self._add(field_type='text', options='Leftover')
        self.assertEqual(RegistrationField.objects.get().options, '')

    def test_form_locked_once_registrations_exist(self):
        question = make_question(self.draft, 'Required one', required=True)
        Registration.objects.create(event=self.draft, student=self.student)
        self.client.force_login(self.org)

        self._add(label='Late question')
        self.client.post(
            reverse('form_field_edit', args=[self.draft.pk, question.pk]),
            {'label': 'Changed', 'field_type': 'text', 'options': '', 'order': 1},
        )
        self.client.post(reverse('form_field_delete', args=[self.draft.pk, question.pk]))

        self.assertEqual(self.draft.registration_fields.count(), 1)
        question.refresh_from_db()
        self.assertEqual(question.label, 'Required one')
        self.assertTrue(question.required)

    def test_existing_answers_preserved_when_locked(self):
        question = make_question(self.draft)
        reg = Registration.objects.create(event=self.draft, student=self.student)
        RegistrationAnswer.objects.create(registration=reg, field=question, answer='Kept')
        self.client.force_login(self.org)
        self.client.post(reverse('form_field_delete', args=[self.draft.pk, question.pk]))
        self.assertEqual(RegistrationAnswer.objects.get().answer, 'Kept')

    def test_form_locked_for_pending_and_approved_events(self):
        self.client.force_login(self.org)
        for status in (Event.PENDING, Event.APPROVED):
            event = make_event(self.org, f'E {status}', status)
            self._add(event=event)
            self.assertEqual(event.registration_fields.count(), 0)


# ---------------------------------------------------------------------------
# Student applications
# ---------------------------------------------------------------------------

class ApplyTests(Base):

    def setUp(self):
        super().setUp()
        self.q_text = make_question(self.approved, 'Why join?', RegistrationField.TEXT, True, order=1)
        self.q_long = make_question(self.approved, 'Anything else?', RegistrationField.TEXTAREA, False, order=2)
        self.q_select = make_question(self.approved, 'Colour', RegistrationField.SELECT, True,
                                      options='Red\nBlue', order=3)
        self.q_num = make_question(self.approved, 'Age', RegistrationField.NUMBER, False, order=4)
        self.q_check = make_question(self.approved, 'Accept rules', RegistrationField.CHECKBOX, True, order=5)
        self.url = reverse('event_register', args=[self.approved.pk])

    def _data(self, **overrides):
        data = {
            k(self.q_text): 'Love the club',
            k(self.q_select): 'Red',
            k(self.q_num): '19',
            k(self.q_check): 'on',
        }
        data.update(overrides)
        return data

    def test_form_page_shows_questions(self):
        self.client.force_login(self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Why join?')
        self.assertContains(response, 'Colour')
        self.assertContains(response, '21CS001')

    def test_participant_can_register(self):
        self.client.force_login(self.student)
        response = self.client.post(self.url, self._data())
        self.assertRedirects(response, reverse('my_registrations'))
        reg = Registration.objects.get(event=self.approved, student=self.student)
        self.assertEqual(reg.answers.get(field=self.q_text).answer, 'Love the club')
        self.assertEqual(reg.answers.get(field=self.q_select).answer, 'Red')
        self.assertEqual(reg.answers.get(field=self.q_num).answer, '19')
        self.assertEqual(reg.answers.get(field=self.q_check).answer, 'Yes')
        self.assertEqual(reg.answers.count(), 5)

    def test_required_question_must_be_answered(self):
        self.client.force_login(self.student)
        response = self.client.post(self.url, self._data(**{k(self.q_text): ''}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Registration.objects.count(), 0)

    def test_required_checkbox_must_be_ticked(self):
        self.client.force_login(self.student)
        data = self._data()
        del data[k(self.q_check)]
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Registration.objects.count(), 0)

    def test_optional_questions_can_be_empty(self):
        self.client.force_login(self.student)
        data = self._data(**{k(self.q_num): '', k(self.q_long): ''})
        self.client.post(self.url, data)
        reg = Registration.objects.get()
        self.assertEqual(reg.answers.get(field=self.q_num).answer, '')
        self.assertEqual(reg.answers.get(field=self.q_long).answer, '')

    def test_dropdown_value_must_match_configured_options(self):
        self.client.force_login(self.student)
        response = self.client.post(self.url, self._data(**{k(self.q_select): 'Green'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Registration.objects.count(), 0)

    def test_number_field_validated(self):
        self.client.force_login(self.student)
        response = self.client.post(self.url, self._data(**{k(self.q_num): 'abc'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Registration.objects.count(), 0)

    def test_duplicate_application_rejected(self):
        self.client.force_login(self.student)
        self.client.post(self.url, self._data())
        response = self.client.post(self.url, self._data(), follow=True)
        self.assertContains(response, 'already registered')
        self.assertEqual(Registration.objects.filter(student=self.student).count(), 1)

    def test_get_for_already_registered_student_redirects(self):
        Registration.objects.create(event=self.approved, student=self.student)
        self.client.force_login(self.student)
        response = self.client.get(self.url)
        self.assertRedirects(
            response, reverse('student_event_detail', args=[self.approved.pk]))

    def test_organizer_and_hod_cannot_apply(self):
        for user in (self.org, self.hod):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url, self._data()).status_code, 403)
        self.assertEqual(Registration.objects.count(), 0)

    def test_anonymous_redirected(self):
        response = self.client.post(self.url, self._data())
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_cannot_apply_to_unapproved_events(self):
        self.client.force_login(self.student)
        for status in (Event.DRAFT, Event.PENDING, Event.REJECTED, Event.COMPLETED):
            event = make_event(self.org, f'E {status}', status)
            response = self.client.post(reverse('event_register', args=[event.pk]), {})
            self.assertEqual(response.status_code, 404, status)
        self.assertEqual(Registration.objects.count(), 0)

    def test_student_identity_comes_from_session(self):
        self.client.force_login(self.student)
        data = self._data(
            student=self.other_student.pk,
            student_id=self.other_student.pk,
            username='stu2',
            email='stu2@example.com',
        )
        self.client.post(self.url, data)
        reg = Registration.objects.get()
        self.assertEqual(reg.student, self.student)

    def test_roll_number_saved_when_account_has_none(self):
        newbie = make_user('newbie', User.PARTICIPANT, 'CSE')
        self.client.force_login(newbie)
        self.client.post(self.url, self._data(roll_number='21CS999'))
        newbie.refresh_from_db()
        self.assertEqual(newbie.roll_number, '21CS999')
        self.assertEqual(Registration.objects.filter(student=newbie).count(), 1)

    def test_roll_number_required_when_account_has_none(self):
        newbie = make_user('newbie', User.PARTICIPANT, 'CSE')
        self.client.force_login(newbie)
        response = self.client.post(self.url, self._data())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Registration.objects.count(), 0)

    def test_roll_number_of_another_account_rejected(self):
        newbie = make_user('newbie', User.PARTICIPANT, 'CSE')
        self.client.force_login(newbie)
        response = self.client.post(self.url, self._data(roll_number='21ec002'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Registration.objects.count(), 0)

    def test_existing_roll_number_cannot_be_overridden(self):
        self.client.force_login(self.student)
        self.client.post(self.url, self._data(roll_number='HACKED'))
        self.student.refresh_from_db()
        self.assertEqual(self.student.roll_number, '21CS001')

    def test_no_partial_registration_when_saving_answers_fails(self):
        form = RegistrationApplicationForm(
            self._data(), event=self.approved, student=self.student)
        self.assertTrue(form.is_valid(), form.errors)
        with mock.patch.object(
                RegistrationAnswer.objects, 'create', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                form.save()
        self.assertEqual(Registration.objects.count(), 0)
        self.assertEqual(RegistrationAnswer.objects.count(), 0)

    def test_event_detail_shows_apply_then_registered_state(self):
        self.client.force_login(self.student)
        detail = reverse('student_event_detail', args=[self.approved.pk])
        response = self.client.get(detail)
        self.assertContains(response, self.url)
        Registration.objects.create(event=self.approved, student=self.student)
        response = self.client.get(detail)
        self.assertContains(response, 'already registered')
        self.assertNotContains(response, 'apply-event-btn')


# ---------------------------------------------------------------------------
# My Registrations
# ---------------------------------------------------------------------------

class MyRegistrationsTests(Base):

    def test_student_sees_only_own_registrations(self):
        other_event = make_event(self.org, 'Other Approved', Event.APPROVED)
        Registration.objects.create(event=self.approved, student=self.student)
        Registration.objects.create(event=other_event, student=self.other_student)
        self.client.force_login(self.student)
        response = self.client.get(reverse('my_registrations'))
        titles = [r.event.title for r in response.context['registrations']]
        self.assertEqual(titles, ['Approved Event'])

    def test_empty_state(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('my_registrations'))
        self.assertContains(response, 'No registrations yet')
        self.assertContains(response, reverse('student_event_list'))

    def test_student_can_view_own_registration_detail(self):
        question = make_question(self.approved, 'Why?')
        reg = Registration.objects.create(event=self.approved, student=self.student)
        RegistrationAnswer.objects.create(registration=reg, field=question, answer='Because')
        self.client.force_login(self.student)
        response = self.client.get(reverse('registration_detail', args=[reg.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Because')

    def test_student_cannot_view_another_students_registration(self):
        reg = Registration.objects.create(event=self.approved, student=self.other_student)
        self.client.force_login(self.student)
        response = self.client.get(reverse('registration_detail', args=[reg.pk]))
        self.assertEqual(response.status_code, 404)

    def test_organizer_and_hod_cannot_open_my_registrations(self):
        for user in (self.org, self.hod):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('my_registrations')).status_code, 403)


# ---------------------------------------------------------------------------
# Organizer applicant lists
# ---------------------------------------------------------------------------

class ApplicantListTests(Base):

    def setUp(self):
        super().setUp()
        self.question = make_question(self.approved, 'Favourite language')
        self.reg = Registration.objects.create(event=self.approved, student=self.student)
        RegistrationAnswer.objects.create(
            registration=self.reg, field=self.question, answer='Python')
        self.url = reverse('applicant_list', args=[self.approved.pk])

    def test_owner_sees_applicants_and_answers(self):
        self.client.force_login(self.org)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['applicant_count'], 1)
        self.assertContains(response, 'Favourite language')
        self.assertContains(response, 'Python')
        self.assertContains(response, '21CS001')
        self.assertContains(response, 'stu1@example.com')

    def test_empty_applicant_list(self):
        self.client.force_login(self.org)
        response = self.client.get(reverse('applicant_list', args=[self.draft.pk]))
        self.assertContains(response, 'No applicants yet')

    def test_other_organizer_forbidden(self):
        self.client.force_login(self.other_org)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_participant_and_hod_forbidden(self):
        for user in (self.student, self.hod):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_owner_can_view_applicant_detail(self):
        self.client.force_login(self.org)
        response = self.client.get(
            reverse('applicant_detail', args=[self.approved.pk, self.reg.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Python')

    def test_other_organizer_cannot_view_applicant_detail(self):
        self.client.force_login(self.other_org)
        response = self.client.get(
            reverse('applicant_detail', args=[self.approved.pk, self.reg.pk]))
        self.assertEqual(response.status_code, 403)

    def test_guessed_registration_id_cannot_bypass_event_ownership(self):
        # The other organizer owns their own event but tries a registration
        # that belongs to someone else's event.
        mine = make_event(self.other_org, 'Mine', Event.APPROVED)
        self.client.force_login(self.other_org)
        response = self.client.get(
            reverse('applicant_detail', args=[mine.pk, self.reg.pk]))
        self.assertEqual(response.status_code, 404)

    def test_event_list_and_detail_show_applicant_links_and_count(self):
        self.client.force_login(self.org)
        response = self.client.get(reverse('event_list'))
        self.assertContains(response, self.url)
        self.assertContains(response, reverse('form_builder', args=[self.approved.pk]))
        response = self.client.get(reverse('event_detail', args=[self.approved.pk]))
        self.assertContains(response, self.url)