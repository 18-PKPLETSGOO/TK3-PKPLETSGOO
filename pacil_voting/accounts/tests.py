from django.test import TestCase
from django.urls import reverse
from .models import CustomUser, LoginAttempt


class LoginRateLimitTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='pemilih1',
            email='pemilih@test.com',
            password='TestPass123!',
            role=CustomUser.ROLE_PEMILIH,
        )

    def test_login_success(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'pemilih@test.com',
            'password': 'TestPass123!',
        })
        self.assertRedirects(response, reverse('home'))

    def test_login_wrong_password_records_attempt(self):
        self.client.post(reverse('accounts:login'), {
            'email': 'pemilih@test.com',
            'password': 'wrong',
        })
        self.assertEqual(LoginAttempt.objects.filter(success=False).count(), 1)

    def test_lockout_after_five_failures(self):
        for _ in range(5):
            self.client.post(reverse('accounts:login'), {
                'email': 'pemilih@test.com',
                'password': 'wrong',
            })
        self.assertTrue(LoginAttempt.is_locked_out('pemilih@test.com'))

    def test_admin_cannot_access_voter_list_when_not_logged_in(self):
        response = self.client.get(reverse('accounts:voter_list'))
        self.assertRedirects(response, reverse('accounts:login'))
