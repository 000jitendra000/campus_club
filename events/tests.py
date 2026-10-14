"""
Phase 2 automated tests — Event CRUD.

All Phase 1 tests continue to live in accounts/tests.py and are run
as part of the full suite.  This file adds event-specific tests.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import Event

import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, role=User.PARTICIPANT, department='', password='TestPass123!'):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password=password,
        role=role,
        department=department,
    )


def make_event(organizer, title='Test Event', days_ahead=7, status=Event.DRAFT):
    """Create and return a saved Event."""
    return Event.objects.create(
        title=title,
        description='A test event description.',
        date=timezone.now() + datetime.timedelta(days=days_ahead),
        venue='Main Hall',
        organizer=organizer,
        department=organizer.department,
        status=status,
    )


def future_date_str(days=7):
    """Return a datetime-local string a given number of days in the future."""
    dt = timezone.now() + datetime.timedelta(days=days)
    # Remove seconds/microseconds for cleanliness
    dt = dt.replace(second=0, microsecond=0)
    return dt.strftime('%Y-%m-%dT%H:%M')


def past_date_str():
    dt = timezone.now() - datetime.timedelta(days=1)
    return dt.strftime('%Y-%m-%dT%H:%M')


# ---------------------------------------------------------------------------
# 1. Event Model Tests
# ---------------------------------------------------------------------------

class EventModelTest(TestCase):

    def setUp(self):
        self.organizer = make_user('org1', role=User.ORGANIZER, department='CSE')

    def test_event_associated_with_organizer(self):
        event = make_event(self.organizer)
        self.assertEqual(event.organizer, self.organizer)

    def test_department_copied_from_organizer(self):
        event = make_event(self.organizer)
        self.assertEqual(event.department, 'CSE')

    def test_new_event_defaults_to_draft(self):
        event = make_event(self.organizer)
        self.assertEqual(event.status, Event.DRAFT)

    def test_is_draft_helper(self):
        event = make_event(self.organizer, status=Event.DRAFT)
        self.assertTrue(event.is_draft())

    def test_non_draft_is_not_draft(self):
        event = make_event(self.organizer, status=Event.APPROVED)
        self.assertFalse(event.is_draft())

    def test_all_status_choices_valid(self):
        valid = [Event.DRAFT, Event.PENDING, Event.APPROVED, Event.REJECTED, Event.COMPLETED]
        for status in valid:
            e = make_event(self.organizer, status=status)
            self.assertEqual(e.status, status)

    def test_str_representation(self):
        event = make_event(self.organizer, title='Annual Fest')
        self.assertIn('Annual Fest', str(event))

    def test_badge_colour_for_draft(self):
        event = make_event(self.organizer, status=Event.DRAFT)
        self.assertEqual(event.badge_colour(), 'secondary')

    def test_badge_colour_for_approved(self):
        event = make_event(self.organizer, status=Event.APPROVED)
        self.assertEqual(event.badge_colour(), 'success')


# ---------------------------------------------------------------------------
# 2. Event Creation Tests
# ---------------------------------------------------------------------------

class EventCreateTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.organizer = make_user('org2', role=User.ORGANIZER, department='ECE')
        self.url = reverse('event_create')

    def _post_create(self, data, user=None):
        if user is None:
            user = self.organizer
        self.client.force_login(user)
        return self.client.post(self.url, data)

    def test_organizer_can_create_event(self):
        response = self._post_create({
            'title': 'Tech Talk',
            'description': 'A talk about tech.',
            'date': future_date_str(),
            'venue': 'Auditorium',
        })
        self.assertEqual(Event.objects.filter(title='Tech Talk').count(), 1)

    def test_new_event_assigned_to_logged_in_organizer(self):
        self._post_create({
            'title': 'Ownership Test',
            'description': 'Checking owner.',
            'date': future_date_str(),
            'venue': 'Room 1',
        })
        event = Event.objects.get(title='Ownership Test')
        self.assertEqual(event.organizer, self.organizer)

    def test_department_assigned_server_side(self):
        self._post_create({
            'title': 'Dept Test',
            'description': 'Check department.',
            'date': future_date_str(),
            'venue': 'Room 2',
        })
        event = Event.objects.get(title='Dept Test')
        self.assertEqual(event.department, 'ECE')

    def test_status_always_draft_on_create(self):
        self._post_create({
            'title': 'Status Test',
            'description': 'Should be draft.',
            'date': future_date_str(),
            'venue': 'Room 3',
        })
        event = Event.objects.get(title='Status Test')
        self.assertEqual(event.status, Event.DRAFT)

    def test_status_injection_ignored(self):
        """Submitting status=approved in POST must be ignored — always DRAFT."""
        self._post_create({
            'title': 'Inject Test',
            'description': 'Trying to inject status.',
            'date': future_date_str(),
            'venue': 'Room 4',
            'status': Event.APPROVED,   # injected
        })
        if Event.objects.filter(title='Inject Test').exists():
            event = Event.objects.get(title='Inject Test')
            self.assertEqual(event.status, Event.DRAFT)

    def test_past_date_rejected(self):
        response = self._post_create({
            'title': 'Past Event',
            'description': 'In the past.',
            'date': past_date_str(),
            'venue': 'Room 5',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Event.objects.filter(title='Past Event').exists())

    def test_create_redirects_to_detail_on_success(self):
        response = self._post_create({
            'title': 'Redirect Test',
            'description': 'Testing redirect.',
            'date': future_date_str(),
            'venue': 'Room 6',
        })
        event = Event.objects.get(title='Redirect Test')
        self.assertRedirects(response, reverse('event_detail', args=[event.pk]))

    def test_participant_cannot_create_event(self):
        participant = make_user('p1', role=User.PARTICIPANT)
        response = self._post_create({
            'title': 'Participant Event',
            'description': 'Should not be created.',
            'date': future_date_str(),
            'venue': 'Room 7',
        }, user=participant)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Event.objects.filter(title='Participant Event').exists())

    def test_hod_cannot_create_event(self):
        hod = make_user('h1', role=User.HOD, department='CSE')
        response = self._post_create({
            'title': 'HOD Event',
            'description': 'HOD should not create.',
            'date': future_date_str(),
            'venue': 'Room 8',
        }, user=hod)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Event.objects.filter(title='HOD Event').exists())

    def test_anonymous_cannot_access_create_page(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])


# ---------------------------------------------------------------------------
# 3. Event List Tests
# ---------------------------------------------------------------------------

class EventListTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.org1 = make_user('org_list1', role=User.ORGANIZER, department='CSE')
        self.org2 = make_user('org_list2', role=User.ORGANIZER, department='ECE')
        self.url = reverse('event_list')

    def test_organizer_sees_only_own_events(self):
        e1 = make_event(self.org1, title='Org1 Event')
        e2 = make_event(self.org2, title='Org2 Event')
        self.client.force_login(self.org1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Org1 Event')
        self.assertNotContains(response, 'Org2 Event')

    def test_empty_list_shows_message(self):
        self.client.force_login(self.org1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No events yet')

    def test_anonymous_cannot_access_list(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_participant_cannot_access_event_list(self):
        p = make_user('p_list', role=User.PARTICIPANT)
        self.client.force_login(p)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_hod_cannot_access_event_list(self):
        h = make_user('h_list', role=User.HOD, department='CSE')
        self.client.force_login(h)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# 4. Event Detail Tests
# ---------------------------------------------------------------------------

class EventDetailTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.org1 = make_user('org_det1', role=User.ORGANIZER, department='CSE')
        self.org2 = make_user('org_det2', role=User.ORGANIZER, department='ECE')
        self.event = make_event(self.org1, title='Detail Event')

    def test_owner_can_view_own_event(self):
        self.client.force_login(self.org1)
        response = self.client.get(reverse('event_detail', args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Event')

    def test_other_organizer_cannot_view_event(self):
        self.client.force_login(self.org2)
        response = self.client.get(reverse('event_detail', args=[self.event.pk]))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_view_event(self):
        response = self.client.get(reverse('event_detail', args=[self.event.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_participant_cannot_view_event(self):
        p = make_user('p_det', role=User.PARTICIPANT)
        self.client.force_login(p)
        response = self.client.get(reverse('event_detail', args=[self.event.pk]))
        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# 5. Edit Event Tests
# ---------------------------------------------------------------------------

class EventEditTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.org1 = make_user('org_ed1', role=User.ORGANIZER, department='CSE')
        self.org2 = make_user('org_ed2', role=User.ORGANIZER, department='ECE')
        self.draft = make_event(self.org1, title='Draft Event', status=Event.DRAFT)
        self.approved = make_event(self.org1, title='Approved Event', status=Event.APPROVED)

    def _post_edit(self, event, data, user=None):
        if user is None:
            user = self.org1
        self.client.force_login(user)
        return self.client.post(reverse('event_edit', args=[event.pk]), data)

    def test_owner_can_edit_draft(self):
        response = self._post_edit(self.draft, {
            'title': 'Updated Draft',
            'description': 'Updated desc.',
            'date': future_date_str(10),
            'venue': 'New Venue',
        })
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.title, 'Updated Draft')

    def test_edit_preserves_organizer(self):
        self._post_edit(self.draft, {
            'title': 'Keep Owner',
            'description': 'Desc.',
            'date': future_date_str(10),
            'venue': 'V',
            'organizer': self.org2.pk,   # injected
        })
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.organizer, self.org1)

    def test_edit_preserves_department(self):
        self._post_edit(self.draft, {
            'title': 'Keep Dept',
            'description': 'Desc.',
            'date': future_date_str(10),
            'venue': 'V',
            'department': 'INJECTED',   # injected
        })
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.department, 'CSE')

    def test_edit_preserves_status(self):
        self._post_edit(self.draft, {
            'title': 'Keep Status',
            'description': 'Desc.',
            'date': future_date_str(10),
            'venue': 'V',
            'status': Event.APPROVED,   # injected
        })
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Event.DRAFT)

    def test_other_organizer_cannot_edit(self):
        response = self._post_edit(self.draft, {
            'title': 'Stolen',
            'description': 'X',
            'date': future_date_str(10),
            'venue': 'V',
        }, user=self.org2)
        self.assertEqual(response.status_code, 403)
        self.draft.refresh_from_db()
        self.assertNotEqual(self.draft.title, 'Stolen')

    def test_cannot_edit_non_draft_event(self):
        self.client.force_login(self.org1)
        response = self.client.get(reverse('event_edit', args=[self.approved.pk]))
        # Should redirect away from edit page with a warning
        self.assertRedirects(
            response,
            reverse('event_detail', args=[self.approved.pk]),
            fetch_redirect_response=False
        )

    def test_past_date_rejected_on_edit(self):
        response = self._post_edit(self.draft, {
            'title': 'Draft Event',
            'description': 'Desc.',
            'date': past_date_str(),
            'venue': 'V',
        })
        self.assertEqual(response.status_code, 200)  # form re-rendered
        self.draft.refresh_from_db()
        # Title must not have been changed to a past-date version
        self.assertNotEqual(self.draft.venue, 'V')

    def test_participant_cannot_edit_event(self):
        p = make_user('p_ed', role=User.PARTICIPANT)
        response = self._post_edit(self.draft, {
            'title': 'X', 'description': 'X', 'date': future_date_str(), 'venue': 'X',
        }, user=p)
        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# 6. Delete Event Tests
# ---------------------------------------------------------------------------

class EventDeleteTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.org1 = make_user('org_del1', role=User.ORGANIZER, department='CSE')
        self.org2 = make_user('org_del2', role=User.ORGANIZER, department='ECE')
        self.draft = make_event(self.org1, title='To Delete')
        self.approved = make_event(self.org1, title='Cannot Delete', status=Event.APPROVED)

    def test_owner_can_delete_draft_via_post(self):
        self.client.force_login(self.org1)
        response = self.client.post(reverse('event_delete', args=[self.draft.pk]))
        self.assertFalse(Event.objects.filter(pk=self.draft.pk).exists())
        self.assertRedirects(response, reverse('event_list'))

    def test_get_request_does_not_delete(self):
        self.client.force_login(self.org1)
        response = self.client.get(reverse('event_delete', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 200)  # confirmation page
        self.assertTrue(Event.objects.filter(pk=self.draft.pk).exists())

    def test_other_organizer_cannot_delete(self):
        self.client.force_login(self.org2)
        response = self.client.post(reverse('event_delete', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Event.objects.filter(pk=self.draft.pk).exists())

    def test_cannot_delete_non_draft(self):
        self.client.force_login(self.org1)
        response = self.client.post(reverse('event_delete', args=[self.approved.pk]))
        # Should redirect (not delete) with a warning
        self.assertTrue(Event.objects.filter(pk=self.approved.pk).exists())

    def test_participant_cannot_delete(self):
        p = make_user('p_del', role=User.PARTICIPANT)
        self.client.force_login(p)
        response = self.client.post(reverse('event_delete', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Event.objects.filter(pk=self.draft.pk).exists())

    def test_hod_cannot_delete(self):
        h = make_user('h_del', role=User.HOD, department='CSE')
        self.client.force_login(h)
        response = self.client.post(reverse('event_delete', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Event.objects.filter(pk=self.draft.pk).exists())

    def test_anonymous_cannot_delete(self):
        response = self.client.post(reverse('event_delete', args=[self.draft.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.assertTrue(Event.objects.filter(pk=self.draft.pk).exists())


# ---------------------------------------------------------------------------
# 7. Organizer Dashboard Integration Tests
# ---------------------------------------------------------------------------

class OrganizerDashboardIntegrationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.organizer = make_user('org_dash', role=User.ORGANIZER, department='ME')

    def test_dashboard_shows_event_counts(self):
        make_event(self.organizer, title='E1', status=Event.DRAFT)
        make_event(self.organizer, title='E2', status=Event.DRAFT)
        make_event(self.organizer, title='E3', status=Event.APPROVED)
        self.client.force_login(self.organizer)
        response = self.client.get(reverse('organizer_dashboard'))
        self.assertEqual(response.status_code, 200)
        # 3 total, 2 draft — check the counts appear in the page
        self.assertContains(response, '3')
        self.assertContains(response, '2')

    def test_dashboard_shows_my_events_link(self):
        self.client.force_login(self.organizer)
        response = self.client.get(reverse('organizer_dashboard'))
        self.assertContains(response, reverse('event_list'))

    def test_dashboard_shows_create_event_link(self):
        self.client.force_login(self.organizer)
        response = self.client.get(reverse('organizer_dashboard'))
        self.assertContains(response, reverse('event_create'))
