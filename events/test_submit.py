"""
Tests for the organizer "Submit for Approval" workflow (DRAFT -> PENDING).
"""

from datetime import timedelta

from django.test import TestCase, Client
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


def make_event(organizer, title='Test Event', status=Event.DRAFT):
    return Event.objects.create(
        title=title,
        description='Test description',
        date=timezone.now() + timedelta(days=7),
        venue='Hall A',
        organizer=organizer,
        department=organizer.department,
        status=status,
    )


class SubmitBaseTest(TestCase):
    def setUp(self):
        self.org = make_user('org_cse', User.ORGANIZER, 'CSE')
        self.other_org = make_user('org_ece', User.ORGANIZER, 'ECE')
        self.hod_cse = make_user('hod_cse', User.HOD, 'CSE')
        self.hod_ece = make_user('hod_ece', User.HOD, 'ECE')
        self.student = make_user('student1', User.PARTICIPANT)
        self.event = make_event(self.org, 'My Draft')

    def _submit(self, event=None, data=None, **kwargs):
        event = event or self.event
        return self.client.post(
            reverse('event_submit', args=[event.pk]), data or {}, **kwargs
        )


# ---------------------------------------------------------------------------
# Successful submission
# ---------------------------------------------------------------------------

class SubmitSuccessTests(SubmitBaseTest):

    def test_owner_can_submit_draft(self):
        self.client.force_login(self.org)
        self._submit()
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.PENDING)

    def test_redirects_to_detail_with_success_message(self):
        self.client.force_login(self.org)
        response = self._submit(follow=True)
        self.assertRedirects(response, reverse('event_detail', args=[self.event.pk]))
        self.assertContains(response, 'submitted for HOD approval')

    def test_organizer_and_department_preserved(self):
        self.client.force_login(self.org)
        self._submit()
        self.event.refresh_from_db()
        self.assertEqual(self.event.organizer, self.org)
        self.assertEqual(self.event.department, 'CSE')

    def test_client_supplied_status_is_ignored(self):
        self.client.force_login(self.org)
        self._submit(data={'status': Event.APPROVED, 'department': 'HACKED'})
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.PENDING)
        self.assertEqual(self.event.department, 'CSE')


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

class SubmitAccessTests(SubmitBaseTest):

    def test_participant_forbidden(self):
        self.client.force_login(self.student)
        self.assertEqual(self._submit().status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.DRAFT)

    def test_hod_forbidden(self):
        self.client.force_login(self.hod_cse)
        self.assertEqual(self._submit().status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.DRAFT)

    def test_anonymous_redirected_to_login(self):
        response = self._submit()
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.DRAFT)

    def test_other_organizer_cannot_submit_event(self):
        self.client.force_login(self.other_org)
        self.assertEqual(self._submit().status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.DRAFT)

    def test_missing_event_returns_404(self):
        self.client.force_login(self.org)
        response = self.client.post(reverse('event_submit', args=[99999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# GET and CSRF
# ---------------------------------------------------------------------------

class SubmitRequestMethodTests(SubmitBaseTest):

    def test_get_does_not_change_status(self):
        self.client.force_login(self.org)
        response = self.client.get(reverse('event_submit', args=[self.event.pk]))
        self.assertEqual(response.status_code, 405)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.DRAFT)

    def test_post_without_csrf_token_is_rejected(self):
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.org)
        response = strict_client.post(reverse('event_submit', args=[self.event.pk]))
        self.assertEqual(response.status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.DRAFT)


# ---------------------------------------------------------------------------
# Repeated submission and non-draft events
# ---------------------------------------------------------------------------

class SubmitStateTests(SubmitBaseTest):

    def test_repeated_submission_is_safe(self):
        self.client.force_login(self.org)
        self._submit()
        response = self._submit(follow=True)
        self.assertContains(response, 'cannot be submitted')
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.PENDING)

    def test_non_draft_events_cannot_be_submitted(self):
        self.client.force_login(self.org)
        for status in (Event.PENDING, Event.APPROVED, Event.REJECTED, Event.COMPLETED):
            event = make_event(self.org, f'Event {status}', status)
            response = self._submit(event=event)
            self.assertRedirects(
                response,
                reverse('event_detail', args=[event.pk]),
                fetch_redirect_response=False,
            )
            event.refresh_from_db()
            self.assertEqual(event.status, status, f'{status} must not change')


# ---------------------------------------------------------------------------
# After submission the event is locked
# ---------------------------------------------------------------------------

class SubmittedEventLockedTests(SubmitBaseTest):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.org)
        self._submit()

    def test_cannot_edit_after_submit(self):
        response = self.client.get(reverse('event_edit', args=[self.event.pk]))
        self.assertRedirects(
            response,
            reverse('event_detail', args=[self.event.pk]),
            fetch_redirect_response=False,
        )

    def test_cannot_edit_via_post_after_submit(self):
        self.client.post(reverse('event_edit', args=[self.event.pk]), {
            'title': 'Changed',
            'description': 'Changed',
            'date': (timezone.now() + timedelta(days=9)).strftime('%Y-%m-%dT%H:%M'),
            'venue': 'Changed',
        })
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'My Draft')

    def test_cannot_delete_after_submit(self):
        self.client.post(reverse('event_delete', args=[self.event.pk]))
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())


# ---------------------------------------------------------------------------
# Button visibility
# ---------------------------------------------------------------------------

class SubmitButtonTests(SubmitBaseTest):

    def test_button_shown_for_draft(self):
        self.client.force_login(self.org)
        response = self.client.get(reverse('event_detail', args=[self.event.pk]))
        self.assertContains(response, 'Submit for Approval')
        self.assertContains(response, reverse('event_submit', args=[self.event.pk]))

    def test_button_hidden_for_pending(self):
        self.event.status = Event.PENDING
        self.event.save()
        self.client.force_login(self.org)
        response = self.client.get(reverse('event_detail', args=[self.event.pk]))
        self.assertNotContains(response, 'Submit for Approval')


# ---------------------------------------------------------------------------
# Full workflow: submit -> HOD sees it -> HOD approves / rejects
# ---------------------------------------------------------------------------

class FullWorkflowTests(SubmitBaseTest):

    def test_submit_then_matching_hod_approves(self):
        self.client.force_login(self.org)
        self._submit()

        self.client.force_login(self.hod_cse)
        response = self.client.get(reverse('hod_event_list'))
        self.assertEqual([e.title for e in response.context['events']], ['My Draft'])

        self.client.post(reverse('hod_event_approve', args=[self.event.pk]))
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.APPROVED)

        self.client.force_login(self.student)
        response = self.client.get(reverse('student_event_list'))
        self.assertEqual([e.title for e in response.context['events']], ['My Draft'])

    def test_submit_then_matching_hod_rejects(self):
        self.client.force_login(self.org)
        self._submit()
        self.client.force_login(self.hod_cse)
        self.client.post(reverse('hod_event_reject', args=[self.event.pk]))
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.REJECTED)

    def test_other_department_hod_does_not_see_submitted_event(self):
        self.client.force_login(self.org)
        self._submit()
        self.client.force_login(self.hod_ece)
        response = self.client.get(reverse('hod_event_list'))
        self.assertEqual(len(response.context['events']), 0)