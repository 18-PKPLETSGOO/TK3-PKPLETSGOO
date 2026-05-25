from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from elections.models import Election
from candidates.models import Candidate


class CandidateEditViewTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        now = timezone.now()
        self.election = Election.objects.create(
            title='Draft Election',
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )
        self.candidate = Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon A', vision='Visi A', mission='Misi A',
        )

    def test_edit_get_renders_form(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('candidates:edit', kwargs={'pk': self.candidate.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_post_valid_updates_candidate(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('candidates:edit', kwargs={'pk': self.candidate.pk}),
            {'number': 1, 'name': 'Updated Paslon', 'vision': 'New Vision', 'mission': 'New Mission'},
        )
        self.assertRedirects(
            response,
            reverse('elections:detail', kwargs={'pk': self.election.pk})
        )
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.name, 'Updated Paslon')

    def test_edit_post_invalid_shows_form(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('candidates:edit', kwargs={'pk': self.candidate.pk}),
            {'number': 150, 'name': '', 'vision': '', 'mission': ''},
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_on_non_draft_election_redirects(self):
        self.election.status = Election.STATUS_OPEN
        self.election.save()
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('candidates:edit', kwargs={'pk': self.candidate.pk})
        )
        self.assertRedirects(
            response,
            reverse('elections:detail', kwargs={'pk': self.election.pk})
        )


class CandidateDeleteViewTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        now = timezone.now()
        self.election = Election.objects.create(
            title='Draft Election',
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )
        self.candidate = Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon A', vision='Visi A', mission='Misi A',
        )

    def test_delete_get_shows_confirm_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('candidates:delete', kwargs={'pk': self.candidate.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_post_removes_candidate(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('candidates:delete', kwargs={'pk': self.candidate.pk})
        )
        self.assertRedirects(
            response,
            reverse('elections:detail', kwargs={'pk': self.election.pk})
        )
        self.assertEqual(Candidate.objects.count(), 0)

    def test_delete_on_non_draft_election_redirects(self):
        self.election.status = Election.STATUS_OPEN
        self.election.save()
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('candidates:delete', kwargs={'pk': self.candidate.pk})
        )
        self.assertRedirects(
            response,
            reverse('elections:detail', kwargs={'pk': self.election.pk})
        )


class CandidateProfileViewTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        now = timezone.now()
        self.election = Election.objects.create(
            title='Draft Election',
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )
        self.candidate_profile = Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon A', vision='Visi A', mission='Misi A',
        )
        self.candidate_user = CustomUser.objects.create_user(
            username='candidateuser',
            email='candidate@test.com',
            password='Candidate123!',
            role=CustomUser.ROLE_CANDIDATE,
        )
        self.candidate_profile.user = self.candidate_user
        self.candidate_profile.save()

    def test_candidate_without_profile_redirects_to_home(self):
        unlinked = CustomUser.objects.create_user(
            username='unlinked',
            email='unlinked@test.com',
            password='Unlinked123!',
            role=CustomUser.ROLE_CANDIDATE,
        )
        self.client.force_login(unlinked)
        response = self.client.get(reverse('candidates:my_profile'))
        self.assertRedirects(response, reverse('home'))

    def test_candidate_profile_get(self):
        self.client.force_login(self.candidate_user)
        response = self.client.get(reverse('candidates:my_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['locked'])

    def test_candidate_profile_post_valid(self):
        self.client.force_login(self.candidate_user)
        response = self.client.post(reverse('candidates:my_profile'), {
            'vision': 'New Vision Updated',
            'mission': 'New Mission Updated',
        })
        self.assertRedirects(response, reverse('candidates:my_profile'))
        self.candidate_profile.refresh_from_db()
        self.assertEqual(self.candidate_profile.vision, 'New Vision Updated')

    def test_candidate_profile_post_invalid(self):
        self.client.force_login(self.candidate_user)
        response = self.client.post(reverse('candidates:my_profile'), {
            'vision': '',
            'mission': '',
        })
        self.assertEqual(response.status_code, 200)

    def test_candidate_profile_locked_when_election_not_draft(self):
        self.election.status = Election.STATUS_OPEN
        self.election.save()
        self.client.force_login(self.candidate_user)
        response = self.client.get(reverse('candidates:my_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['locked'])

    def test_candidate_profile_post_blocked_when_locked(self):
        self.election.status = Election.STATUS_OPEN
        self.election.save()
        self.client.force_login(self.candidate_user)
        response = self.client.post(reverse('candidates:my_profile'), {
            'vision': 'Changed Vision',
            'mission': 'Changed Mission',
        })
        self.assertRedirects(response, reverse('candidates:my_profile'))
        self.candidate_profile.refresh_from_db()
        self.assertEqual(self.candidate_profile.vision, 'Visi A')
