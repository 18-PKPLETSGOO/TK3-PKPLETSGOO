"""
elections/tests/test_security_gaps.py
Gap tests for the elections app — closes gap #7.

Gap addressed
  #7  elections/views.py:67-131  All election state transitions were untested.
      Broken guards allow editing live elections, opening with insufficient
      candidates, or reopening closed elections — all compromising integrity.

Run:
    python manage.py test elections.tests.test_security_gaps -v 2
"""

from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from elections.models import Election
from candidates.models import Candidate


# ─── shared helper ────────────────────────────────────────────────

def _make_user(username, email, password, role):
    user = CustomUser.objects.create_user(
        username=username, email=email, password=password,
    )
    user.role = role
    user.save()
    return user


def _make_draft_election(admin, title='Test Election'):
    return Election.objects.create(
        title=title,
        description='For state transition testing',
        start_date=timezone.now() - timedelta(hours=1),
        end_date=timezone.now() + timedelta(hours=1),
        status=Election.STATUS_DRAFT,
        created_by=admin,
    )


def _add_candidates(election, count=2):
    """Add `count` candidates to the election and return the list."""
    candidates = []
    for i in range(1, count + 1):
        candidates.append(Candidate.objects.create(
            election=election, number=i,
            name=f'Paslon {i}', vision=f'Visi {i}', mission=f'Misi {i}',
        ))
    return candidates


# ═══════════════════════════════════════════════════════════════════
# GAP #7 — Election state transitions (views.py:67-131)
# ═══════════════════════════════════════════════════════════════════

class ElectionStateTransitionSecurityTest(TestCase):
    """
    Gap #7: All election state transitions (open, close, edit) were completely
    untested.  Broken guards allow:
      • Editing a live election (changes rules mid-vote)
      • Opening an election with <2 candidates (empty/single-choice ballot)
      • Reopening a closed election (new votes after the official count)
    All of these directly compromise election integrity.
    """

    def setUp(self):
        self.client = Client()
        self.admin = _make_user(
            'admin_st', 'admin_st@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.voter = _make_user(
            'voter_st', 'voter_st@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )

    # ── TC-ST-01: Open guards ────────────────────────────────────────

    def test_cannot_open_election_with_zero_candidates(self):
        """
        Gap #7: election_open_view requires candidates.count() >= 2.
        Opening a zero-candidate election produces an empty ballot — voters
        would see no choices and the integrity of the process is undefined.
        """
        election = _make_draft_election(self.admin, 'Zero Cand Election')
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:open', kwargs={'pk': election.pk}))

        election.refresh_from_db()
        self.assertEqual(
            election.status, Election.STATUS_DRAFT,
            "Election with 0 candidates must remain DRAFT after open attempt.",
        )

    def test_cannot_open_election_with_one_candidate(self):
        """
        Gap #7: The 2-candidate minimum guard must fire for exactly 1 candidate.
        A single-candidate election is not a meaningful vote.
        """
        election = _make_draft_election(self.admin, 'One Cand Election')
        _add_candidates(election, count=1)
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:open', kwargs={'pk': election.pk}))

        election.refresh_from_db()
        self.assertEqual(
            election.status, Election.STATUS_DRAFT,
            "Election with 1 candidate must remain DRAFT after open attempt.",
        )

    def test_can_open_election_with_two_candidates(self):
        """
        Gap #7 (positive): 2 candidates satisfies the minimum — election must
        transition to OPEN and remain OPEN after the state change.
        """
        election = _make_draft_election(self.admin, 'Two Cand Election')
        _add_candidates(election, count=2)
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:open', kwargs={'pk': election.pk}))

        election.refresh_from_db()
        self.assertEqual(
            election.status, Election.STATUS_OPEN,
            "Election with 2 candidates must transition to OPEN.",
        )

    def test_can_open_election_with_more_than_two_candidates(self):
        """
        Gap #7 (positive): 3 candidates is also valid — verify no off-by-one error
        in the '>= 2' guard.
        """
        election = _make_draft_election(self.admin, 'Three Cand Election')
        _add_candidates(election, count=3)
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:open', kwargs={'pk': election.pk}))

        election.refresh_from_db()
        self.assertEqual(
            election.status, Election.STATUS_OPEN,
            "Election with 3 candidates must transition to OPEN.",
        )

    # ── TC-ST-02: Edit guards ────────────────────────────────────────

    def test_cannot_edit_open_election(self):
        """
        Gap #7: Editing a live (OPEN) election changes the title/description
        visible to voters mid-vote, which could manipulate their choices.
        The edit guard must redirect without saving changes.
        """
        election = _make_draft_election(self.admin, 'Edit Guard OPEN')
        _add_candidates(election, count=2)
        # Manually set OPEN (bypass the open view's date/candidate check)
        election.status = Election.STATUS_OPEN
        election.save()

        self.client.force_login(self.admin)
        original_title = election.title
        self.client.post(
            reverse('elections:edit', kwargs={'pk': election.pk}),
            {
                'title': 'TAMPERED TITLE',
                'description': 'Tampered',
                'start_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': (timezone.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
            },
        )
        election.refresh_from_db()
        self.assertEqual(
            election.title, original_title,
            "SECURITY FINDING: OPEN election title was changed — edit guard broken!",
        )
        self.assertEqual(
            election.status, Election.STATUS_OPEN,
            "Election status must remain OPEN after rejected edit attempt.",
        )

    def test_cannot_edit_closed_election(self):
        """
        Gap #7: A CLOSED election is a historical record.  Allowing edits would
        let an admin retroactively alter official election information.
        """
        election = _make_draft_election(self.admin, 'Edit Guard CLOSED')
        _add_candidates(election, count=2)
        election.status = Election.STATUS_CLOSED
        election.save()

        self.client.force_login(self.admin)
        original_title = election.title
        self.client.post(
            reverse('elections:edit', kwargs={'pk': election.pk}),
            {
                'title': 'RETROACTIVE TAMPER',
                'description': 'Tampered description',
                'start_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': (timezone.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
            },
        )
        election.refresh_from_db()
        self.assertEqual(
            election.title, original_title,
            "SECURITY FINDING: CLOSED election title was changed — retroactive edit possible!",
        )

    # ── TC-ST-03: Close ──────────────────────────────────────────────

    def test_can_close_open_election(self):
        """
        Gap #7 (positive): Admin must be able to close an OPEN election.
        Verifies the close transition works end-to-end.
        """
        election = _make_draft_election(self.admin, 'Close Test Election')
        _add_candidates(election, count=2)
        election.status = Election.STATUS_OPEN
        election.save()

        self.client.force_login(self.admin)
        self.client.post(reverse('elections:close', kwargs={'pk': election.pk}))

        election.refresh_from_db()
        self.assertEqual(
            election.status, Election.STATUS_CLOSED,
            "Admin must be able to close an OPEN election (status must become CLOSED).",
        )

    def test_cannot_reopen_closed_election(self):
        """
        Gap #7: Reopening a closed election would allow new votes after the
        official count has been recorded.  The open guard requires STATUS_DRAFT;
        a CLOSED election must be permanently sealed.
        """
        election = _make_draft_election(self.admin, 'Reopen Guard Election')
        _add_candidates(election, count=2)
        election.status = Election.STATUS_CLOSED
        election.save()

        self.client.force_login(self.admin)
        self.client.post(reverse('elections:open', kwargs={'pk': election.pk}))

        election.refresh_from_db()
        self.assertEqual(
            election.status, Election.STATUS_CLOSED,
            "SECURITY FINDING: Closed election was reopened — vote stuffing possible!",
        )

    def test_cannot_close_draft_election(self):
        """
        Gap #7: Closing a DRAFT election that was never opened would silently
        short-circuit the election process.  Only OPEN elections may be closed.
        """
        election = _make_draft_election(self.admin, 'Close Draft Guard')
        self.client.force_login(self.admin)
        self.client.post(reverse('elections:close', kwargs={'pk': election.pk}))

        election.refresh_from_db()
        self.assertEqual(
            election.status, Election.STATUS_DRAFT,
            "DRAFT election must remain DRAFT after a close attempt.",
        )

    # ── TC-ST-04: Access control ─────────────────────────────────────

    def test_non_admin_cannot_open_election(self):
        """
        Gap #7 (RBAC): Only admin may change election state.  A voter calling
        the open endpoint is a critical access control failure — it could
        trigger a premature election opening.
        """
        election = _make_draft_election(self.admin, 'RBAC Open Guard')
        _add_candidates(election, count=2)

        self.client.force_login(self.voter)
        self.client.post(reverse('elections:open', kwargs={'pk': election.pk}))

        election.refresh_from_db()
        self.assertEqual(
            election.status, Election.STATUS_DRAFT,
            "SECURITY FINDING: Non-admin opened an election — RBAC guard broken!",
        )

    def test_non_admin_cannot_close_election(self):
        """
        Gap #7 (RBAC): A voter calling the close endpoint could prematurely
        stop an active election, disenfranchising voters still in the process
        of casting their ballots.
        """
        election = _make_draft_election(self.admin, 'RBAC Close Guard')
        _add_candidates(election, count=2)
        election.status = Election.STATUS_OPEN
        election.save()

        self.client.force_login(self.voter)
        self.client.post(reverse('elections:close', kwargs={'pk': election.pk}))

        election.refresh_from_db()
        self.assertEqual(
            election.status, Election.STATUS_OPEN,
            "SECURITY FINDING: Non-admin closed an election — RBAC guard broken!",
        )

    def test_non_admin_cannot_edit_election(self):
        """
        Gap #7 (RBAC): A voter calling election-edit must be blocked.
        Unauthorized edits to election metadata are a data integrity violation.
        """
        election = _make_draft_election(self.admin, 'RBAC Edit Guard')
        original_title = election.title

        self.client.force_login(self.voter)
        response = self.client.post(
            reverse('elections:edit', kwargs={'pk': election.pk}),
            {
                'title': 'VOTER TAMPERED',
                'description': '',
                'start_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': (timezone.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
            },
        )
        self.assertIn(
            response.status_code, [302, 403],
            "Non-admin edit must return 302 or 403.",
        )
        election.refresh_from_db()
        self.assertEqual(
            election.title, original_title,
            "SECURITY FINDING: Voter changed election title — edit RBAC guard broken!",
        )
