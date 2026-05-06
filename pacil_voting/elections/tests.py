from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from .models import Election


class ElectionModelTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        now = timezone.now()
        self.election = Election.objects.create(
            title='Pemilu Test',
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            status=Election.STATUS_OPEN,
            created_by=self.admin,
        )

    def test_is_active_when_open_and_within_dates(self):
        self.assertTrue(self.election.is_active)

    def test_not_active_when_draft(self):
        self.election.status = Election.STATUS_DRAFT
        self.election.save()
        self.assertFalse(self.election.is_active)

    def test_not_active_when_closed(self):
        self.election.status = Election.STATUS_CLOSED
        self.election.save()
        self.assertFalse(self.election.is_active)


class ElectionAccessTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        self.pemilih = CustomUser.objects.create_user(
            username='pemilih', email='pemilih@test.com',
            password='Pemilih123!', role=CustomUser.ROLE_PEMILIH,
        )

    def test_pemilih_cannot_access_create_election(self):
        self.client.force_login(self.pemilih)
        response = self.client.get(reverse('elections:create'))
        self.assertRedirects(response, reverse('home'))

    def test_admin_can_access_create_election(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('elections:create'))
        self.assertEqual(response.status_code, 200)
