from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser
from candidates.models import Candidate
from elections.models import Election
from elections.forms import ElectionForm


class ElectionCreateViewTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )

    def _dates(self, delta_start=1, delta_end=2):
        now = timezone.now()
        return {
            'start_date': (now + timedelta(days=delta_start)).strftime('%Y-%m-%dT%H:%M'),
            'end_date': (now + timedelta(days=delta_end)).strftime('%Y-%m-%dT%H:%M'),
        }

    def test_create_election_post_valid(self):
        self.client.force_login(self.admin)
        data = {'title': 'New Election', 'description': 'Deskripsi pemilihan'}
        data.update(self._dates())
        response = self.client.post(reverse('elections:create'), data)
        self.assertEqual(Election.objects.count(), 1)
        election = Election.objects.first()
        self.assertRedirects(response, reverse('elections:detail', kwargs={'pk': election.pk}))

    def test_create_election_post_invalid(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('elections:create'), {
            'title': '',
            'description': '',
            'start_date': '',
            'end_date': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Election.objects.count(), 0)


class ElectionEditViewTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        now = timezone.now()
        self.draft_election = Election.objects.create(
            title='Draft Election',
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )
        self.open_election = Election.objects.create(
            title='Open Election',
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            status=Election.STATUS_OPEN,
            created_by=self.admin,
        )

    def test_edit_non_draft_redirects(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('elections:edit', kwargs={'pk': self.open_election.pk})
        )
        self.assertRedirects(
            response,
            reverse('elections:detail', kwargs={'pk': self.open_election.pk})
        )

    def test_edit_get_renders_form(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('elections:edit', kwargs={'pk': self.draft_election.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_post_valid(self):
        self.client.force_login(self.admin)
        now = timezone.now()
        response = self.client.post(
            reverse('elections:edit', kwargs={'pk': self.draft_election.pk}),
            {
                'title': 'Updated Election',
                'description': 'Updated desc',
                'start_date': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
                'end_date': (now + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            }
        )
        self.assertRedirects(
            response,
            reverse('elections:detail', kwargs={'pk': self.draft_election.pk})
        )
        self.draft_election.refresh_from_db()
        self.assertEqual(self.draft_election.title, 'Updated Election')

    def test_edit_post_invalid(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('elections:edit', kwargs={'pk': self.draft_election.pk}),
            {'title': '', 'start_date': '', 'end_date': ''}
        )
        self.assertEqual(response.status_code, 200)


class ElectionOpenViewTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        now = timezone.now()
        self.election = Election.objects.create(
            title='Test Election',
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )
        Candidate.objects.create(
            election=self.election, number=1, name='Paslon A', vision='V', mission='M'
        )
        Candidate.objects.create(
            election=self.election, number=2, name='Paslon B', vision='V', mission='M'
        )

    def test_open_get_renders_confirm_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('elections:open', kwargs={'pk': self.election.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_open_post_not_draft_keeps_status(self):
        self.election.status = Election.STATUS_OPEN
        self.election.save()
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:open', kwargs={'pk': self.election.pk}))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, Election.STATUS_OPEN)

    def test_open_post_insufficient_candidates_keeps_draft(self):
        Candidate.objects.filter(election=self.election).last().delete()
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:open', kwargs={'pk': self.election.pk}))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, Election.STATUS_DRAFT)

    def test_open_post_success(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:open', kwargs={'pk': self.election.pk}))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, Election.STATUS_OPEN)


class ElectionCloseViewTest(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin', email='admin@test.com',
            password='Admin123!', role=CustomUser.ROLE_ADMIN,
        )
        now = timezone.now()
        self.election = Election.objects.create(
            title='Open Election',
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            status=Election.STATUS_OPEN,
            created_by=self.admin,
        )

    def test_close_get_renders_confirm_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('elections:close', kwargs={'pk': self.election.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_close_post_not_open_keeps_status(self):
        self.election.status = Election.STATUS_DRAFT
        self.election.save()
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:close', kwargs={'pk': self.election.pk}))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, Election.STATUS_DRAFT)

    def test_close_post_success(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:close', kwargs={'pk': self.election.pk}))
        self.election.refresh_from_db()
        self.assertEqual(self.election.status, Election.STATUS_CLOSED)


class ElectionFormTest(TestCase):
    def _base_data(self, **overrides):
        now = timezone.now()
        data = {
            'title': 'Pemilihan Valid',
            'description': 'Deskripsi singkat',
            'start_date': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_date': (now + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = ElectionForm(data=self._base_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_title_with_invalid_chars_rejected(self):
        # Use { } which survives html.escape but is still blocked by clean_title regex
        form = ElectionForm(data=self._base_data(title='Judul{Buruk}'))
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_description_too_long_rejected(self):
        form = ElectionForm(data=self._base_data(description='x' * 2001))
        self.assertFalse(form.is_valid())
        self.assertIn('description', form.errors)

    def test_start_date_equal_to_end_date_rejected(self):
        now = timezone.now()
        same = (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        form = ElectionForm(data=self._base_data(start_date=same, end_date=same))
        self.assertFalse(form.is_valid())

    def test_start_date_after_end_date_rejected(self):
        now = timezone.now()
        form = ElectionForm(data=self._base_data(
            start_date=(now + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            end_date=(now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
        ))
        self.assertFalse(form.is_valid())
