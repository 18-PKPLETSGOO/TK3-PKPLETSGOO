from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from elections.models import Election
from candidates.models import Candidate
from voting.models import Vote


class CastVoteViewTest(TestCase):
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
            title='Test Election', created_by=self.admin,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            status=Election.STATUS_OPEN,
        )
        self.candidate1 = Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon A', vision='Visi', mission='Misi',
        )
        self.candidate2 = Candidate.objects.create(
            election=self.election, number=2,
            name='Paslon B', vision='Visi', mission='Misi',
        )

    def test_cast_vote_get_renders_form(self):
        self.client.force_login(self.pemilih)
        response = self.client.get(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_cast_vote_post_valid_creates_vote(self):
        self.client.force_login(self.pemilih)
        response = self.client.post(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk}),
            {'candidate': self.candidate1.pk},
        )
        self.assertRedirects(
            response,
            reverse('voting:status', kwargs={'election_pk': self.election.pk})
        )
        self.assertEqual(Vote.objects.count(), 1)

    def test_cast_vote_post_no_candidate_shows_form(self):
        self.client.force_login(self.pemilih)
        response = self.client.post(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk}),
            {},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Vote.objects.count(), 0)

    def test_cast_vote_already_voted_redirects_to_status(self):
        Vote.objects.create(
            voter=self.pemilih,
            election=self.election,
            candidate=self.candidate1,
        )
        self.client.force_login(self.pemilih)
        response = self.client.get(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk})
        )
        self.assertRedirects(
            response,
            reverse('voting:status', kwargs={'election_pk': self.election.pk})
        )


class VoteStatusViewTest(TestCase):
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
            title='Test Election', created_by=self.admin,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            status=Election.STATUS_OPEN,
        )
        self.candidate = Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon A', vision='Visi', mission='Misi',
        )

    def test_vote_status_view_no_vote(self):
        self.client.force_login(self.pemilih)
        response = self.client.get(
            reverse('voting:status', kwargs={'election_pk': self.election.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['vote'])

    def test_vote_status_view_after_voting(self):
        vote = Vote.objects.create(
            voter=self.pemilih,
            election=self.election,
            candidate=self.candidate,
        )
        self.client.force_login(self.pemilih)
        response = self.client.get(
            reverse('voting:status', kwargs={'election_pk': self.election.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['vote'], vote)
