"""
Tests for HOD department-specific review and student browsing of events.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import Event


def make_user(username, role, department=''):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='TestPass123!',
        role=role,
        department=department,
    )


def make_event(organizer, title, status=Event.DRAFT):
    return Event.objects.create(
        title=title,
        description='Test description',
        date=timezone.now() + timedelta(days=7),
        venue='Hall A',
        organizer=organizer,
        department=organizer.department,
        status=status,
    )


class BaseReviewTest(TestCase):
    def setUp(self):
        self.hod_cse = make_user('hod_cse', User.HOD, 'CSE')
        self.hod_ece = make_user('hod_ece', User.HOD, 'ECE')
        self.org_cse = make_user('org_cse', User.ORGANIZER, 'CSE')
        self.org_ece = make_user('org_ece', User.ORGANIZER, 'ECE')
        self.student = make_user('student1', User.PARTICIPANT)


# ---------------------------------------------------------------------------
# HOD review list
# ---------------------------------------------------------------------------

class HODReviewListTests(BaseReviewTest):

    def setUp(self):
        super().setUp()
        self.url = reverse('hod_event_list')

    def test_hod_sees_only_pending_events_from_own_department(self):
        make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        make_event(self.org_ece, 'ECE Pending', Event.PENDING)
        make_event(self.org_cse, 'CSE Draft', Event.DRAFT)
        make_event(self.org_cse, 'CSE Approved', Event.APPROVED)

        self.client.force_login(self.hod_cse)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        titles = [e.title for e in response.context['events']]
        self.assertEqual(titles, ['CSE Pending'])

    def test_department_match_ignores_case(self):
        make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        hod_lower = make_user('hod_lower', User.HOD, 'cse')
        self.client.force_login(hod_lower)
        response = self.client.get(self.url)
        titles = [e.title for e in response.context['events']]
        self.assertEqual(titles, ['CSE Pending'])

    def test_hod_without_department_sees_nothing(self):
        org_blank = make_user('org_blank', User.ORGANIZER, '')
        make_event(org_blank, 'Blank Dept Pending', Event.PENDING)
        hod_blank = make_user('hod_blank', User.HOD, '')
        self.client.force_login(hod_blank)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['events']), 0)

    def test_organizer_forbidden(self):
        self.client.force_login(self.org_cse)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_student_forbidden(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])


# ---------------------------------------------------------------------------
# HOD detail
# ---------------------------------------------------------------------------

class HODDetailTests(BaseReviewTest):

    def test_hod_can_view_own_department_pending_event(self):
        event = make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        self.client.force_login(self.hod_cse)
        response = self.client.get(reverse('hod_event_detail', args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CSE Pending')

    def test_hod_cannot_view_other_department_event(self):
        event = make_event(self.org_ece, 'ECE Pending', Event.PENDING)
        self.client.force_login(self.hod_cse)
        response = self.client.get(reverse('hod_event_detail', args=[event.pk]))
        self.assertEqual(response.status_code, 403)

    def test_hod_cannot_view_draft_event(self):
        event = make_event(self.org_cse, 'CSE Draft', Event.DRAFT)
        self.client.force_login(self.hod_cse)
        response = self.client.get(reverse('hod_event_detail', args=[event.pk]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# HOD approve / reject
# ---------------------------------------------------------------------------

class HODActionTests(BaseReviewTest):

    def _approve(self, event):
        return self.client.post(reverse('hod_event_approve', args=[event.pk]))

    def _reject(self, event):
        return self.client.post(reverse('hod_event_reject', args=[event.pk]))

    def test_hod_can_approve_pending_event_in_own_department(self):
        event = make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        self.client.force_login(self.hod_cse)
        response = self._approve(event)
        self.assertRedirects(response, reverse('hod_event_list'))
        event.refresh_from_db()
        self.assertEqual(event.status, Event.APPROVED)

    def test_hod_can_reject_pending_event_in_own_department(self):
        event = make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        self.client.force_login(self.hod_cse)
        response = self._reject(event)
        self.assertRedirects(response, reverse('hod_event_list'))
        event.refresh_from_db()
        self.assertEqual(event.status, Event.REJECTED)

    def test_hod_cannot_approve_other_department_event(self):
        event = make_event(self.org_ece, 'ECE Pending', Event.PENDING)
        self.client.force_login(self.hod_cse)
        self.assertEqual(self._approve(event).status_code, 403)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.PENDING)

    def test_hod_cannot_reject_other_department_event(self):
        event = make_event(self.org_ece, 'ECE Pending', Event.PENDING)
        self.client.force_login(self.hod_cse)
        self.assertEqual(self._reject(event).status_code, 403)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.PENDING)

    def test_hod_cannot_approve_draft(self):
        event = make_event(self.org_cse, 'CSE Draft', Event.DRAFT)
        self.client.force_login(self.hod_cse)
        self.assertEqual(self._approve(event).status_code, 404)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.DRAFT)

    def test_approved_event_cannot_be_rejected_later(self):
        event = make_event(self.org_cse, 'CSE Approved', Event.APPROVED)
        self.client.force_login(self.hod_cse)
        self._reject(event)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.APPROVED)

    def test_rejected_event_cannot_be_approved_later(self):
        event = make_event(self.org_cse, 'CSE Rejected', Event.REJECTED)
        self.client.force_login(self.hod_cse)
        self._approve(event)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.REJECTED)

    def test_get_request_not_allowed_for_approve(self):
        event = make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        self.client.force_login(self.hod_cse)
        response = self.client.get(reverse('hod_event_approve', args=[event.pk]))
        self.assertEqual(response.status_code, 405)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.PENDING)

    def test_organizer_cannot_approve(self):
        event = make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        self.client.force_login(self.org_cse)
        self.assertEqual(self._approve(event).status_code, 403)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.PENDING)

    def test_student_cannot_approve(self):
        event = make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        self.client.force_login(self.student)
        self.assertEqual(self._approve(event).status_code, 403)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.PENDING)

    def test_anonymous_cannot_approve(self):
        event = make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        response = self._approve(event)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        event.refresh_from_db()
        self.assertEqual(event.status, Event.PENDING)

    def test_hod_without_department_cannot_approve_blank_department_event(self):
        org_blank = make_user('org_blank', User.ORGANIZER, '')
        event = make_event(org_blank, 'Blank Pending', Event.PENDING)
        hod_blank = make_user('hod_blank', User.HOD, '')
        self.client.force_login(hod_blank)
        self.assertEqual(self._approve(event).status_code, 403)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.PENDING)


# ---------------------------------------------------------------------------
# Student browsing
# ---------------------------------------------------------------------------

class StudentBrowseTests(BaseReviewTest):

    def test_student_list_shows_only_approved_events(self):
        make_event(self.org_cse, 'Visible Approved', Event.APPROVED)
        make_event(self.org_cse, 'Hidden Draft', Event.DRAFT)
        make_event(self.org_cse, 'Hidden Pending', Event.PENDING)
        make_event(self.org_cse, 'Hidden Rejected', Event.REJECTED)

        self.client.force_login(self.student)
        response = self.client.get(reverse('student_event_list'))

        self.assertEqual(response.status_code, 200)
        titles = [e.title for e in response.context['events']]
        self.assertEqual(titles, ['Visible Approved'])

    def test_student_list_shows_approved_events_from_all_departments(self):
        make_event(self.org_cse, 'CSE Approved', Event.APPROVED)
        make_event(self.org_ece, 'ECE Approved', Event.APPROVED)
        self.client.force_login(self.student)
        response = self.client.get(reverse('student_event_list'))
        self.assertEqual(len(response.context['events']), 2)

    def test_student_can_view_approved_event_detail(self):
        event = make_event(self.org_cse, 'Approved Event', Event.APPROVED)
        self.client.force_login(self.student)
        response = self.client.get(reverse('student_event_detail', args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Approved Event')

    def test_student_cannot_view_non_approved_event_detail(self):
        self.client.force_login(self.student)
        for status in (Event.DRAFT, Event.PENDING, Event.REJECTED):
            event = make_event(self.org_cse, f'Event {status}', status)
            response = self.client.get(reverse('student_event_detail', args=[event.pk]))
            self.assertEqual(response.status_code, 404, f'{status} should be hidden')

    def test_organizer_cannot_use_student_browse(self):
        event = make_event(self.org_cse, 'Approved Event', Event.APPROVED)
        self.client.force_login(self.org_cse)
        self.assertEqual(self.client.get(reverse('student_event_list')).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('student_event_detail', args=[event.pk])).status_code, 403
        )

    def test_hod_cannot_use_student_browse(self):
        event = make_event(self.org_cse, 'Approved Event', Event.APPROVED)
        self.client.force_login(self.hod_cse)
        self.assertEqual(self.client.get(reverse('student_event_list')).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('student_event_detail', args=[event.pk])).status_code, 403
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('student_event_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])


# ---------------------------------------------------------------------------
# Dashboards still work
# ---------------------------------------------------------------------------

class DashboardTests(BaseReviewTest):

    def test_hod_dashboard_shows_pending_count_for_own_department(self):
        make_event(self.org_cse, 'CSE Pending', Event.PENDING)
        make_event(self.org_ece, 'ECE Pending', Event.PENDING)
        self.client.force_login(self.hod_cse)
        response = self.client.get(reverse('hod_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pending_count'], 1)

    def test_participant_and_organizer_dashboards_load(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('participant_dashboard')).status_code, 200)
        self.client.force_login(self.org_cse)
        self.assertEqual(self.client.get(reverse('organizer_dashboard')).status_code, 200)