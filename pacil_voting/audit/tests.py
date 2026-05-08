from django.test import TestCase
from django.urls import reverse
from accounts.models import CustomUser
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
