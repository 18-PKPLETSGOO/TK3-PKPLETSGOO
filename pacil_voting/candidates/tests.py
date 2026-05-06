from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from elections.models import Election
from .models import Candidate


class CandidateModelTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        now = timezone.now()
        self.election = Election.objects.create(
            title='Pemilu Test',
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )

    def test_admin_can_add_candidate_to_draft_election(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse('candidates:create', kwargs={'election_pk': self.election.pk}),
            {'number': 1, 'name': 'Paslon A', 'vision': 'Visi A', 'mission': 'Misi A'},
        )
        self.assertEqual(Candidate.objects.count(), 1)

    def test_cannot_add_candidate_to_open_election(self):
        self.election.status = Election.STATUS_OPEN
        self.election.save()
        self.client.force_login(self.admin)
        self.client.post(
            reverse('candidates:create', kwargs={'election_pk': self.election.pk}),
            {'number': 1, 'name': 'Paslon A', 'vision': 'Visi A', 'mission': 'Misi A'},
        )
        self.assertEqual(Candidate.objects.count(), 0)
