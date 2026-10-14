"""
Tests for attendance tracking.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
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


def make_event(organizer, title='Event', status=Event.APPROVED):
    return Event.objects.create(
        title=title,
        description='Description',
        date=timezone.now() + timedelta(days=7),
        venue='Hall A',
        organizer=organizer,
        department=organizer.department,
        status=status,
    )


class AttendanceBase(TestCase):
    def setUp(self):
        self.org = make_user('org1', User.ORGANIZER, 'CSE')
        self.other_org = make_user('org2', User.ORGANIZER, 'ECE')
        self.hod = make_user('hod1', User.HOD, 'CSE')
        self.s1 = make_user('stu1', User.PARTICIPANT, 'CSE', '21CS001')
        self.s2 = make_user('stu2', User.PARTICIPANT, 'CSE', '21CS002')
        self.s3 = make_user('stu3', User.PARTICIPANT, 'ECE', '21EC003')

        self.event = make_event(self.org, 'Approved Event')
        self.reg1 = Registration.objects.create(event=self.event, student=self.s1)
        self.reg2 = Registration.objects.create(event=self.event, student=self.s2)
        self.reg3 = Registration.objects.create(event=self.event, student=self.s3)

        self.url = reverse('attendance', args=[self.event.pk])

    def _mark(self, registration, status, event=None, **extra):
        event = event or self.event
        data = {'status': status}
        data.update(extra)
        return self.client.post(
            reverse('attendance_mark', args=[event.pk, registration.pk]), data
        )


# ---------------------------------------------------------------------------
# Marking
# ---------------------------------------------------------------------------

class MarkAttendanceTests(AttendanceBase):

    def test_new_registrations_are_not_marked(self):
        for reg in (self.reg1, self.reg2, self.reg3):
            reg.refresh_from_db()
            self.assertEqual(reg.attendance_status, Registration.NOT_MARKED)
            self.assertIsNone(reg.attendance_marked_at)

    def test_viewing_page_does_not_mark_anyone(self):
        self.client.force_login(self.org)
        self.client.get(self.url)
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_status, Registration.NOT_MARKED)

    def test_owner_can_mark_present(self):
        self.client.force_login(self.org)
        response = self._mark(self.reg1, 'present')
        self.assertRedirects(response, self.url)
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_status, Registration.PRESENT)
        self.assertIsNotNone(self.reg1.attendance_marked_at)
        self.assertEqual(self.reg1.attendance_marked_by, self.org)

    def test_owner_can_mark_absent(self):
        self.client.force_login(self.org)
        self._mark(self.reg2, 'absent')
        self.reg2.refresh_from_db()
        self.assertEqual(self.reg2.attendance_status, Registration.ABSENT)

    def test_marking_one_student_does_not_affect_others(self):
        self.client.force_login(self.org)
        self._mark(self.reg1, 'present')
        self.reg2.refresh_from_db()
        self.assertEqual(self.reg2.attendance_status, Registration.NOT_MARKED)

    def test_attendance_can_be_corrected(self):
        self.client.force_login(self.org)
        self._mark(self.reg1, 'present')
        self.reg1.refresh_from_db()
        first_time = self.reg1.attendance_marked_at

        self._mark(self.reg1, 'absent')
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_status, Registration.ABSENT)
        self.assertGreaterEqual(self.reg1.attendance_marked_at, first_time)

        self._mark(self.reg1, 'present')
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_status, Registration.PRESENT)

    def test_invalid_values_rejected(self):
        self.client.force_login(self.org)
        for bad in ('hacked', 'not_marked', '', 'PRESENT '):
            response = self._mark(self.reg1, bad)
            self.assertEqual(response.status_code, 302)
            self.reg1.refresh_from_db()
            self.assertEqual(self.reg1.attendance_status, Registration.NOT_MARKED, bad)

    def test_missing_status_rejected(self):
        self.client.force_login(self.org)
        self.client.post(reverse('attendance_mark', args=[self.event.pk, self.reg1.pk]))
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_status, Registration.NOT_MARKED)

    def test_browser_cannot_set_marker_or_timestamp(self):
        self.client.force_login(self.org)
        self._mark(
            self.reg1, 'present',
            attendance_marked_by=self.other_org.pk,
            attendance_marked_at='2000-01-01 00:00:00',
        )
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_marked_by, self.org)
        self.assertGreater(self.reg1.attendance_marked_at.year, 2000)

    def test_get_request_does_not_mark(self):
        self.client.force_login(self.org)
        response = self.client.get(
            reverse('attendance_mark', args=[self.event.pk, self.reg1.pk]))
        self.assertEqual(response.status_code, 405)
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_status, Registration.NOT_MARKED)

    def test_marking_keeps_registration_and_answers(self):
        question = RegistrationField.objects.create(event=self.event, label='Why?')
        RegistrationAnswer.objects.create(
            registration=self.reg1, field=question, answer='Because')
        self.client.force_login(self.org)
        self._mark(self.reg1, 'present')
        self._mark(self.reg1, 'absent')
        self.assertEqual(Registration.objects.filter(event=self.event).count(), 3)
        self.assertEqual(self.reg1.answers.get().answer, 'Because')


# ---------------------------------------------------------------------------
# Counts and filter
# ---------------------------------------------------------------------------

class AttendanceCountsTests(AttendanceBase):

    def test_counts_are_correct(self):
        self.client.force_login(self.org)
        self._mark(self.reg1, 'present')
        self._mark(self.reg2, 'absent')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        counts = response.context['counts']
        self.assertEqual(counts['total'], 3)
        self.assertEqual(counts['present'], 1)
        self.assertEqual(counts['absent'], 1)
        self.assertEqual(counts['not_marked'], 1)

    def test_counts_only_include_this_event(self):
        other_event = make_event(self.org, 'Other Event')
        Registration.objects.create(event=other_event, student=self.s1)
        self.client.force_login(self.org)
        response = self.client.get(self.url)
        self.assertEqual(response.context['counts']['total'], 3)

    def test_unmarked_filter(self):
        self.client.force_login(self.org)
        self._mark(self.reg1, 'present')
        response = self.client.get(self.url + '?filter=unmarked')
        shown = {r.pk for r in response.context['registrations']}
        self.assertEqual(shown, {self.reg2.pk, self.reg3.pk})

    def test_empty_event_shows_empty_state(self):
        empty = make_event(self.org, 'Empty Event')
        self.client.force_login(self.org)
        response = self.client.get(reverse('attendance', args=[empty.pk]))
        self.assertContains(response, 'No registered students')


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class AttendancePermissionTests(AttendanceBase):

    def test_other_organizer_cannot_view_or_mark(self):
        self.client.force_login(self.other_org)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self._mark(self.reg1, 'present').status_code, 403)
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_status, Registration.NOT_MARKED)

    def test_participant_and_hod_cannot_access(self):
        for user in (self.s1, self.hod):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self._mark(self.reg1, 'present').status_code, 403)
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_status, Registration.NOT_MARKED)

    def test_anonymous_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        response = self._mark(self.reg1, 'present')
        self.assertEqual(response.status_code, 302)
        self.reg1.refresh_from_db()
        self.assertEqual(self.reg1.attendance_status, Registration.NOT_MARKED)

    def test_registration_from_another_event_is_rejected(self):
        # A registration that belongs to a different event, owned by someone else.
        foreign_event = make_event(self.other_org, 'Foreign Event')
        foreign_reg = Registration.objects.create(event=foreign_event, student=self.s1)
        self.client.force_login(self.org)
        response = self._mark(foreign_reg, 'present')   # posted to MY event's URL
        self.assertEqual(response.status_code, 404)
        foreign_reg.refresh_from_db()
        self.assertEqual(foreign_reg.attendance_status, Registration.NOT_MARKED)

    def test_registration_from_another_own_event_is_rejected(self):
        second_event = make_event(self.org, 'Second Event')
        second_reg = Registration.objects.create(event=second_event, student=self.s1)
        self.client.force_login(self.org)
        response = self._mark(second_reg, 'present')    # wrong event URL
        self.assertEqual(response.status_code, 404)
        second_reg.refresh_from_db()
        self.assertEqual(second_reg.attendance_status, Registration.NOT_MARKED)


# ---------------------------------------------------------------------------
# Event status rules
# ---------------------------------------------------------------------------

class AttendanceEventStatusTests(AttendanceBase):

    def test_not_available_for_draft_pending_or_rejected(self):
        self.client.force_login(self.org)
        for status in (Event.DRAFT, Event.PENDING, Event.REJECTED):
            event = make_event(self.org, f'E {status}', status)
            reg = Registration.objects.create(event=event, student=self.s1)

            response = self.client.get(reverse('attendance', args=[event.pk]))
            self.assertRedirects(
                response, reverse('event_detail', args=[event.pk]),
                fetch_redirect_response=False)

            self._mark(reg, 'present', event=event)
            reg.refresh_from_db()
            self.assertEqual(reg.attendance_status, Registration.NOT_MARKED, status)

    def test_available_for_completed_events(self):
        event = make_event(self.org, 'Done', Event.COMPLETED)
        reg = Registration.objects.create(event=event, student=self.s1)
        self.client.force_login(self.org)
        self.assertEqual(
            self.client.get(reverse('attendance', args=[event.pk])).status_code, 200)
        self._mark(reg, 'present', event=event)
        reg.refresh_from_db()
        self.assertEqual(reg.attendance_status, Registration.PRESENT)


# ---------------------------------------------------------------------------
# What students and organizers see elsewhere
# ---------------------------------------------------------------------------

class AttendanceVisibilityTests(AttendanceBase):

    def test_unmarked_shows_as_not_marked_not_absent(self):
        self.client.force_login(self.s1)
        response = self.client.get(reverse('my_registrations'))
        self.assertContains(response, 'Not Marked')
        self.assertNotContains(response, 'Absent')

    def test_student_sees_own_attendance_only(self):
        self.client.force_login(self.org)
        self._mark(self.reg1, 'present')
        self._mark(self.reg2, 'absent')

        self.client.force_login(self.s1)
        response = self.client.get(reverse('my_registrations'))
        regs = list(response.context['registrations'])
        self.assertEqual([r.pk for r in regs], [self.reg1.pk])
        self.assertContains(response, 'Present')
        self.assertNotContains(response, 'Absent')

    def test_student_detail_shows_own_attendance(self):
        self.client.force_login(self.org)
        self._mark(self.reg1, 'present')
        self.client.force_login(self.s1)
        response = self.client.get(reverse('registration_detail', args=[self.reg1.pk]))
        self.assertContains(response, 'Present')

    def test_student_cannot_see_another_students_registration(self):
        self.client.force_login(self.s1)
        response = self.client.get(reverse('registration_detail', args=[self.reg2.pk]))
        self.assertEqual(response.status_code, 404)

    def test_applicant_list_shows_attendance(self):
        self.client.force_login(self.org)
        self._mark(self.reg1, 'present')
        response = self.client.get(reverse('applicant_list', args=[self.event.pk]))
        self.assertContains(response, 'Present')
        self.assertContains(response, 'Not Marked')

    def test_organizer_pages_link_to_attendance(self):
        self.client.force_login(self.org)
        response = self.client.get(reverse('event_list'))
        self.assertContains(response, self.url)
        response = self.client.get(reverse('event_detail', args=[self.event.pk]))
        self.assertContains(response, self.url)