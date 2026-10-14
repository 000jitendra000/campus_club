"""
Automated tests for Phase 1 of Campus Club.

Covers:
  - User model (role storage, department persistence)
  - Student registration (valid, role enforcement, duplicate username/email,
    password mismatch, weak password, malicious role injection)
  - Authentication (valid login, invalid login, logout, redirect to dashboard)
  - Authorization (anonymous users, cross-role dashboard access)
"""

from django.test import TestCase, Client
from django.urls import reverse

from .models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, role=User.PARTICIPANT, department='', password='TestPass123!'):
    """Factory helper — creates and returns a saved User."""
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password=password,
        role=role,
        department=department,
    )
    return user


# ---------------------------------------------------------------------------
# 1. User Model Tests
# ---------------------------------------------------------------------------

class UserModelRoleTest(TestCase):
    """Each role can be stored and retrieved correctly."""

    def test_organizer_role_stored(self):
        user = make_user('organizer1', role=User.ORGANIZER, department='CSE')
        user.refresh_from_db()
        self.assertEqual(user.role, User.ORGANIZER)

    def test_participant_role_stored(self):
        user = make_user('student1', role=User.PARTICIPANT)
        user.refresh_from_db()
        self.assertEqual(user.role, User.PARTICIPANT)

    def test_hod_role_stored(self):
        user = make_user('hod1', role=User.HOD, department='ECE')
        user.refresh_from_db()
        self.assertEqual(user.role, User.HOD)

    def test_department_stored_correctly(self):
        user = make_user('organizer2', role=User.ORGANIZER, department='Mechanical')
        user.refresh_from_db()
        self.assertEqual(user.department, 'Mechanical')

    def test_blank_department_allowed_for_participant(self):
        user = make_user('student2', role=User.PARTICIPANT, department='')
        user.refresh_from_db()
        self.assertEqual(user.department, '')

    def test_is_organizer_helper(self):
        user = make_user('org3', role=User.ORGANIZER)
        self.assertTrue(user.is_organizer())
        self.assertFalse(user.is_participant())
        self.assertFalse(user.is_hod())

    def test_is_participant_helper(self):
        user = make_user('s3', role=User.PARTICIPANT)
        self.assertTrue(user.is_participant())

    def test_is_hod_helper(self):
        user = make_user('hod3', role=User.HOD)
        self.assertTrue(user.is_hod())


# ---------------------------------------------------------------------------
# 2. Registration Tests
# ---------------------------------------------------------------------------

class StudentRegistrationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('register')

    def _post_register(self, data):
        return self.client.post(self.url, data)

    def test_valid_registration_succeeds(self):
        response = self._post_register({
            'username': 'newstudent',
            'email': 'newstudent@example.com',
            'department': 'CSE',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newstudent').exists())

    def test_new_public_account_always_participant(self):
        self._post_register({
            'username': 'studentx',
            'email': 'studentx@example.com',
            'department': '',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        user = User.objects.get(username='studentx')
        self.assertEqual(user.role, User.PARTICIPANT)

    def test_malicious_role_injection_organizer(self):
        """Sending role=organizer in POST must be ignored — result is always PARTICIPANT."""
        response = self._post_register({
            'username': 'hacker1',
            'email': 'hacker1@example.com',
            'department': 'CSE',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'role': 'organizer',          # injected extra field
        })
        if User.objects.filter(username='hacker1').exists():
            user = User.objects.get(username='hacker1')
            self.assertEqual(user.role, User.PARTICIPANT,
                             'Injected role=organizer must be ignored.')

    def test_malicious_role_injection_hod(self):
        self._post_register({
            'username': 'hacker2',
            'email': 'hacker2@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'role': 'hod',
        })
        if User.objects.filter(username='hacker2').exists():
            user = User.objects.get(username='hacker2')
            self.assertNotEqual(user.role, User.HOD)

    def test_duplicate_username_rejected(self):
        make_user('existing')
        response = self._post_register({
            'username': 'existing',
            'email': 'other@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')

    def test_duplicate_email_rejected(self):
        make_user('user_a')  # email = user_a@example.com
        response = self._post_register({
            'username': 'user_b',
            'email': 'user_a@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='user_b').exists())

    def test_password_mismatch_rejected(self):
        response = self._post_register({
            'username': 'mismatch',
            'email': 'mismatch@example.com',
            'password1': 'SecurePass123!',
            'password2': 'DifferentPass456!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='mismatch').exists())

    def test_weak_password_rejected(self):
        """Django's NumericPasswordValidator should reject all-digit passwords."""
        response = self._post_register({
            'username': 'weakpwd',
            'email': 'weakpwd@example.com',
            'password1': '12345678',
            'password2': '12345678',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='weakpwd').exists())

    def test_registration_redirects_to_login(self):
        response = self._post_register({
            'username': 'redirect_test',
            'email': 'redirect_test@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        self.assertRedirects(response, reverse('login'))

    def test_authenticated_user_cannot_register_again(self):
        user = make_user('already_in')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('dashboard_redirect'), fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# 3. Authentication Tests
# ---------------------------------------------------------------------------

class AuthenticationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = make_user('loginuser', role=User.PARTICIPANT)
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')

    def test_valid_login_succeeds(self):
        response = self.client.post(self.login_url, {
            'username': 'loginuser',
            'password': 'TestPass123!',
        })
        self.assertRedirects(response, reverse('dashboard_redirect'), fetch_redirect_response=False)

    def test_invalid_login_fails(self):
        response = self.client.post(self.login_url, {
            'username': 'loginuser',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')

    def test_logout_works(self):
        self.client.force_login(self.user)
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, self.login_url)
        # After logout the user should not be authenticated
        response = self.client.get(reverse('participant_dashboard'))
        self.assertRedirects(response, f'/accounts/login/?next=/dashboard/participant/')

    def test_login_redirects_participant_to_participant_dashboard(self):
        self.client.post(self.login_url, {
            'username': 'loginuser',
            'password': 'TestPass123!',
        })
        response = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(response, reverse('participant_dashboard'))

    def test_login_redirects_organizer_to_organizer_dashboard(self):
        org = make_user('orguser', role=User.ORGANIZER)
        self.client.post(self.login_url, {
            'username': 'orguser',
            'password': 'TestPass123!',
        })
        response = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(response, reverse('organizer_dashboard'))

    def test_login_redirects_hod_to_hod_dashboard(self):
        hod = make_user('hoduser', role=User.HOD)
        self.client.post(self.login_url, {
            'username': 'hoduser',
            'password': 'TestPass123!',
        })
        response = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(response, reverse('hod_dashboard'))

    def test_already_authenticated_redirected_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(self.login_url)
        self.assertRedirects(response, reverse('dashboard_redirect'), fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# 4. Authorization Tests
# ---------------------------------------------------------------------------

class AuthorizationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.participant = make_user('part', role=User.PARTICIPANT)
        self.organizer = make_user('org', role=User.ORGANIZER, department='CSE')
        self.hod = make_user('hod', role=User.HOD, department='CSE')

        self.urls = {
            'organizer': reverse('organizer_dashboard'),
            'participant': reverse('participant_dashboard'),
            'hod': reverse('hod_dashboard'),
        }

    # Anonymous access
    def test_anonymous_cannot_access_participant_dashboard(self):
        r = self.client.get(self.urls['participant'])
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_anonymous_cannot_access_organizer_dashboard(self):
        r = self.client.get(self.urls['organizer'])
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_anonymous_cannot_access_hod_dashboard(self):
        r = self.client.get(self.urls['hod'])
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    # Participant cross-role
    def test_participant_cannot_access_organizer_dashboard(self):
        self.client.force_login(self.participant)
        r = self.client.get(self.urls['organizer'])
        self.assertEqual(r.status_code, 403)

    def test_participant_cannot_access_hod_dashboard(self):
        self.client.force_login(self.participant)
        r = self.client.get(self.urls['hod'])
        self.assertEqual(r.status_code, 403)

    def test_participant_can_access_own_dashboard(self):
        self.client.force_login(self.participant)
        r = self.client.get(self.urls['participant'])
        self.assertEqual(r.status_code, 200)

    # Organizer cross-role
    def test_organizer_cannot_access_participant_dashboard(self):
        self.client.force_login(self.organizer)
        r = self.client.get(self.urls['participant'])
        self.assertEqual(r.status_code, 403)

    def test_organizer_cannot_access_hod_dashboard(self):
        self.client.force_login(self.organizer)
        r = self.client.get(self.urls['hod'])
        self.assertEqual(r.status_code, 403)

    def test_organizer_can_access_own_dashboard(self):
        self.client.force_login(self.organizer)
        r = self.client.get(self.urls['organizer'])
        self.assertEqual(r.status_code, 200)

    # HOD cross-role
    def test_hod_cannot_access_organizer_dashboard(self):
        self.client.force_login(self.hod)
        r = self.client.get(self.urls['organizer'])
        self.assertEqual(r.status_code, 403)

    def test_hod_cannot_access_participant_dashboard(self):
        self.client.force_login(self.hod)
        r = self.client.get(self.urls['participant'])
        self.assertEqual(r.status_code, 403)

    def test_hod_can_access_own_dashboard(self):
        self.client.force_login(self.hod)
        r = self.client.get(self.urls['hod'])
        self.assertEqual(r.status_code, 200)
