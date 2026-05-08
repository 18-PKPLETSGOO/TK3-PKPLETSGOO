from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from elections.models import Election
from candidates.models import Candidate
from .models import Vote


class VoteModelTest(TestCase):
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
        self.election = Election.objects.create(
            title='Pemilu Test', created_by=self.admin,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            status=Election.STATUS_OPEN,
        )
        self.candidate = Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon A', vision='Visi', mission='Misi',
        )

    def test_anonymous_token_generated_on_save(self):
        vote = Vote.objects.create(
            voter=self.pemilih, election=self.election, candidate=self.candidate,
        )
        self.assertTrue(len(vote.anonymous_token) == 64)

    def test_double_voting_prevented_by_unique_together(self):
        Vote.objects.create(
            voter=self.pemilih, election=self.election, candidate=self.candidate,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Vote.objects.create(
                voter=self.pemilih, election=self.election, candidate=self.candidate,
            )

    def test_pemilih_cannot_vote_on_inactive_election(self):
        self.election.status = Election.STATUS_DRAFT
        self.election.save()
        self.client.force_login(self.pemilih)
        response = self.client.post(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk}),
            {'candidate': self.candidate.pk},
        )
        self.assertEqual(Vote.objects.count(), 0)
