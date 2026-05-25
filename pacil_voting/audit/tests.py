from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from elections.models import Election
from .models import AuditLog


class AuditLogModelTest(TestCase):
    def test_log_hash_computed_on_save(self):
        log = AuditLog.log(action=AuditLog.ACTION_LOGIN, details={'test': True})
        self.assertTrue(len(log.log_hash) == 64)

    def test_log_hash_is_deterministic_sha256(self):
        log = AuditLog.log(action=AuditLog.ACTION_LOGOUT)
        self.assertRegex(log.log_hash, r'^[a-f0-9]{64}$')


class AuditLogViewTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        self.pemilih = CustomUser.objects.create_user(
            username='pemilih', email='pemilih@test.com',
            password='Pemilih123!', role=CustomUser.ROLE_PEMILIH,
        )

    def test_admin_can_access_audit_logs(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('audit:logs'))
        self.assertEqual(response.status_code, 200)

    def test_pemilih_cannot_access_audit_logs(self):
        self.client.force_login(self.pemilih)
        response = self.client.get(reverse('audit:logs'))
        self.assertRedirects(response, reverse('home'))


class ResultsViewTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        self.pemilih = CustomUser.objects.create_user(
            username='pemilih', email='pemilih@test.com',
            password='Pemilih123!', role=CustomUser.ROLE_PEMILIH,
        )
        now = timezone.now()
        self.closed_election = Election.objects.create(
            title='Closed Election',
            start_date=now - timedelta(hours=2),
            end_date=now - timedelta(hours=1),
            status=Election.STATUS_CLOSED,
            created_by=self.admin,
        )
        self.open_election = Election.objects.create(
            title='Open Election',
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            status=Election.STATUS_OPEN,
            created_by=self.admin,
        )

    def test_admin_can_see_results_of_closed_election(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('audit:results', kwargs={'election_pk': self.closed_election.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.context)

    def test_admin_can_see_results_of_open_election(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('audit:results', kwargs={'election_pk': self.open_election.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.context)

    def test_pemilih_can_see_results_of_closed_election(self):
        self.client.force_login(self.pemilih)
        response = self.client.get(
            reverse('audit:results', kwargs={'election_pk': self.closed_election.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.context)

    def test_pemilih_sees_pending_page_for_open_election(self):
        self.client.force_login(self.pemilih)
        response = self.client.get(
            reverse('audit:results', kwargs={'election_pk': self.open_election.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'audit/results_pending.html')

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(
            reverse('audit:results', kwargs={'election_pk': self.closed_election.pk})
        )
        self.assertEqual(response.status_code, 302)
