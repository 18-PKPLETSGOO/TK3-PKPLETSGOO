from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser, LoginAttempt
from elections.models import Election
from candidates.models import Candidate


class LoginViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='TestPass123!',
            role=CustomUser.ROLE_PEMILIH,
        )

    def test_login_get_renders_form(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_login_get_shows_lockout_for_locked_account(self):
        for _ in range(5):
            LoginAttempt.objects.create(
                email='test@test.com',
                ip_address='127.0.0.1',
                success=False,
            )
        session = self.client.session
        session['locked_email'] = 'test@test.com'
        session.save()
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get('locked_out'))

    def test_login_post_already_locked_out(self):
        for _ in range(5):
            LoginAttempt.objects.create(
                email='test@test.com',
                ip_address='127.0.0.1',
                success=False,
            )
        response = self.client.post(reverse('accounts:login'), {
            'email': 'test@test.com',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get('locked_out'))

    def test_login_fifth_failure_triggers_lockout(self):
        for _ in range(4):
            LoginAttempt.objects.create(
                email='test@test.com',
                ip_address='127.0.0.1',
                success=False,
            )
        response = self.client.post(reverse('accounts:login'), {
            'email': 'test@test.com',
            'password': 'wrongpass',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get('locked_out'))

    def test_login_post_invalid_form(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'not-valid-email',
            'password': '',
        })
        self.assertEqual(response.status_code, 200)


class LogoutViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='logoutuser',
            email='logout@test.com',
            password='TestPass123!',
            role=CustomUser.ROLE_PEMILIH,
        )

    def test_logout_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))

    def test_logout_unauthenticated_user(self):
        response = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))


class VoterManagementTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='Admin123!',
            role=CustomUser.ROLE_ADMIN,
        )
        self.voter = CustomUser.objects.create_user(
            username='voter1',
            email='voter1@test.com',
            password='Voter123!',
            role=CustomUser.ROLE_PEMILIH,
            nim='12345',
        )

    def test_voter_list_accessible_by_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:voter_list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.voter, response.context['voters'])

    def test_add_voter_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:add_voter'))
        self.assertEqual(response.status_code, 200)

    def test_add_voter_post_valid(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('accounts:add_voter'), {
            'email': 'newvoter@test.com',
            'first_name': 'New',
            'last_name': 'Voter',
            'nim': '99001',
            'username': 'newvoter',
            'password': 'Qwerty123!',
            'password_confirm': 'Qwerty123!',
        })
        self.assertRedirects(response, reverse('accounts:voter_list'))
        self.assertTrue(CustomUser.objects.filter(email='newvoter@test.com').exists())

    def test_add_voter_post_invalid(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('accounts:add_voter'), {
            'email': 'bad-email',
            'first_name': '',
            'last_name': '',
            'nim': '',
            'username': '',
            'password': '123',
            'password_confirm': '456',
        })
        self.assertEqual(response.status_code, 200)

    def test_delete_voter_get_shows_confirm_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('accounts:delete_voter', kwargs={'pk': self.voter.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_voter_post_removes_voter(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('accounts:delete_voter', kwargs={'pk': self.voter.pk})
        )
        self.assertRedirects(response, reverse('accounts:voter_list'))
        self.assertFalse(CustomUser.objects.filter(pk=self.voter.pk).exists())


class CandidateUserManagementTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='Admin123!',
            role=CustomUser.ROLE_ADMIN,
        )
        now = timezone.now()
        self.election = Election.objects.create(
            title='Pemilu Test',
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )
        self.unassigned_candidate = Candidate.objects.create(
            election=self.election,
            number=1,
            name='Paslon A',
            vision='Visi A',
            mission='Misi A',
        )

    def test_candidate_user_list_accessible_by_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:candidate_user_list'))
        self.assertEqual(response.status_code, 200)

    def test_add_candidate_user_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:add_candidate_user'))
        self.assertEqual(response.status_code, 200)

    def test_add_candidate_user_post_valid(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('accounts:add_candidate_user'), {
            'email': 'newcand@test.com',
            'first_name': 'New',
            'last_name': 'Candidate',
            'username': 'newcand',
            'password': 'Qwerty123!',
            'password_confirm': 'Qwerty123!',
            'candidate': self.unassigned_candidate.pk,
        })
        self.assertRedirects(response, reverse('accounts:candidate_user_list'))
        self.assertTrue(CustomUser.objects.filter(email='newcand@test.com').exists())

    def test_add_candidate_user_post_invalid(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('accounts:add_candidate_user'), {
            'email': 'bad-email',
            'first_name': '',
            'last_name': '',
            'username': '',
            'password': '123',
            'password_confirm': '456',
        })
        self.assertEqual(response.status_code, 200)
