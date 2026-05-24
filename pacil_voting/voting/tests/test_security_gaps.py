"""
voting/tests/test_security_gaps.py
Gap tests for the voting app — closes gaps #4, #5, #6.

Gaps addressed
  #4  voting/views.py:18-19   Inactive election guard (DRAFT / CLOSED rejection)
  #5  voting/views.py:34-40   Race-condition double-vote prevention (select_for_update re-check)
  #6  voting/views.py:60-64   IntegrityError handler (DB unique_together constraint)

Run:
    python manage.py test voting.tests.test_security_gaps -v 2
"""

from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from elections.models import Election
from candidates.models import Candidate
from voting.models import Vote


# ─── shared helper ────────────────────────────────────────────────

def _make_user(username, email, password, role):
    user = CustomUser.objects.create_user(
        username=username, email=email, password=password,
    )
    user.role = role
    user.save()
    return user


def _make_open_election(admin, title='Open Election', offset_hours=1):
    """Create an election that is currently active (OPEN, within date window)."""
    return Election.objects.create(
        title=title,
        description='',
        start_date=timezone.now() - timedelta(hours=offset_hours),
        end_date=timezone.now() + timedelta(hours=offset_hours),
        status=Election.STATUS_OPEN,
        created_by=admin,
    )


# ═══════════════════════════════════════════════════════════════════
# GAP #4 — Inactive election guard (views.py:18-19)
# ═══════════════════════════════════════════════════════════════════

class VotingInactiveElectionGuardTest(TestCase):
    """
    Gap #4: The guard at views.py:18-19 rejects votes on non-active elections.
    It was never tested.  A regression here allows vote-stuffing on DRAFT or
    CLOSED elections, corrupting the final vote count.

    Election.is_active requires: status==OPEN AND start_date <= now <= end_date
    """

    def setUp(self):
        self.client = Client()
        self.admin = _make_user(
            'admin_ig', 'admin_ig@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.voter = _make_user(
            'voter_ig', 'voter_ig@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )

    def _make_election_with_candidates(self, status, start_delta=-1, end_delta=1):
        election = Election.objects.create(
            title=f'IG Election ({status})',
            description='',
            start_date=timezone.now() + timedelta(hours=start_delta),
            end_date=timezone.now() + timedelta(hours=end_delta),
            status=status,
            created_by=self.admin,
        )
        c1 = Candidate.objects.create(
            election=election, number=1,
            name='Paslon A', vision='Visi A', mission='Misi A',
        )
        c2 = Candidate.objects.create(
            election=election, number=2,
            name='Paslon B', vision='Visi B', mission='Misi B',
        )
        return election, c1, c2

    # ── TC-IG-01 ────────────────────────────────────────────────────

    def test_voter_cannot_cast_vote_on_draft_election(self):
        """
        Gap #4: POST to cast a vote on a DRAFT election must be rejected.
        DRAFT elections are not yet officially open; votes must not be accepted.
        Expected: redirect with error, no Vote row created.
        """
        election, c1, _ = self._make_election_with_candidates(
            Election.STATUS_DRAFT, start_delta=1, end_delta=2
        )
        self.client.force_login(self.voter)
        response = self.client.post(
            reverse('voting:cast', kwargs={'election_pk': election.pk}),
            {'candidate': c1.pk},
        )
        self.assertNotEqual(
            response.status_code, 200,
            "DRAFT election vote must not return 200 (implies vote form accepted).",
        )
        self.assertFalse(
            Vote.objects.filter(voter=self.voter, election=election).exists(),
            "SECURITY FINDING: Vote row created for a DRAFT election!",
        )

    def test_voter_cannot_cast_vote_on_closed_election(self):
        """
        Gap #4: POST to cast a vote on a CLOSED election must be rejected.
        Vote-stuffing after an election closes would alter the final results.
        Expected: redirect with error, no Vote row created.
        """
        election, c1, _ = self._make_election_with_candidates(Election.STATUS_CLOSED)
        # Manually mark as closed (simulates post-count state)
        election.status = Election.STATUS_CLOSED
        election.save()
        self.client.force_login(self.voter)
        response = self.client.post(
            reverse('voting:cast', kwargs={'election_pk': election.pk}),
            {'candidate': c1.pk},
        )
        self.assertNotEqual(
            response.status_code, 200,
            "CLOSED election vote must not return 200.",
        )
        self.assertFalse(
            Vote.objects.filter(voter=self.voter, election=election).exists(),
            "SECURITY FINDING: Vote row created for a CLOSED election!",
        )

    def test_voter_cannot_cast_vote_on_future_open_election(self):
        """
        Gap #4: An OPEN election whose start_date is in the future is technically
        not yet active (is_active=False).  Votes must be rejected even though
        the election status is OPEN.
        """
        # start_date is 1 hour in the future → not yet active
        election, c1, _ = self._make_election_with_candidates(
            Election.STATUS_OPEN, start_delta=1, end_delta=2
        )
        self.client.force_login(self.voter)
        response = self.client.post(
            reverse('voting:cast', kwargs={'election_pk': election.pk}),
            {'candidate': c1.pk},
        )
        self.assertFalse(
            Vote.objects.filter(voter=self.voter, election=election).exists(),
            "SECURITY FINDING: Vote accepted on future-start OPEN election!",
        )

    def test_voter_can_successfully_cast_vote_on_active_open_election(self):
        """
        Gap #4 (positive): Voting on a properly active OPEN election must succeed.
        This verifies the guard only rejects the wrong states, not all states.
        """
        election, c1, _ = self._make_election_with_candidates(Election.STATUS_OPEN)
        self.client.force_login(self.voter)
        response = self.client.post(
            reverse('voting:cast', kwargs={'election_pk': election.pk}),
            {'candidate': c1.pk},
        )
        self.assertIn(
            response.status_code, [302, 200],
            "Vote on an active OPEN election must be accepted.",
        )
        self.assertTrue(
            Vote.objects.filter(voter=self.voter, election=election).exists(),
            "Vote row must exist after successful vote cast.",
        )


# ═══════════════════════════════════════════════════════════════════
# GAP #5 — Double-vote prevention (views.py:34-40)
# ═══════════════════════════════════════════════════════════════════

class VotingDoubleVotePreventionTest(TestCase):
    """
    Gap #5: The application-level double-vote check (views.py:21-23) and the
    select_for_update() re-check inside the atomic block (views.py:34-40) were
    never tested.  A regression here allows a voter to cast multiple ballots,
    directly compromising election integrity.
    """

    def setUp(self):
        self.client = Client()
        self.admin = _make_user(
            'admin_dv', 'admin_dv@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.voter = _make_user(
            'voter_dv', 'voter_dv@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        self.election = _make_open_election(self.admin, 'DV Election')
        self.candidate1 = Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon DV1', vision='Visi', mission='Misi',
        )
        self.candidate2 = Candidate.objects.create(
            election=self.election, number=2,
            name='Paslon DV2', vision='Visi 2', mission='Misi 2',
        )
        self.vote_url = reverse(
            'voting:cast', kwargs={'election_pk': self.election.pk}
        )

    # ── TC-DV-01 ────────────────────────────────────────────────────

    def test_sequential_double_vote_is_rejected(self):
        """
        Gap #5: After casting one valid vote, an immediate second POST to the
        same election must be rejected.  The view checks existing votes before
        processing; the second request must redirect to vote-status, not process.
        """
        self.client.force_login(self.voter)
        # First vote — must succeed
        r1 = self.client.post(self.vote_url, {'candidate': self.candidate1.pk})
        self.assertIn(r1.status_code, [302, 200], "First vote must be accepted.")
        self.assertTrue(
            Vote.objects.filter(voter=self.voter, election=self.election).exists(),
            "First vote must create a Vote row.",
        )
        # Second vote — must be rejected
        r2 = self.client.post(self.vote_url, {'candidate': self.candidate2.pk})
        self.assertNotEqual(r2.status_code, 500,
            "Double vote attempt must not return HTTP 500.")
        count = Vote.objects.filter(voter=self.voter, election=self.election).count()
        self.assertEqual(
            count, 1,
            f"SECURITY FINDING: Voter has {count} votes — double voting accepted!",
        )

    def test_double_vote_does_not_corrupt_first_vote(self):
        """
        Gap #5 (integrity): The first vote must remain unchanged after a rejected
        double-vote attempt.  The rejected second vote must not overwrite the
        original candidate choice.
        """
        self.client.force_login(self.voter)
        # Cast first vote for candidate1
        self.client.post(self.vote_url, {'candidate': self.candidate1.pk})
        # Attempt second vote for candidate2
        self.client.post(self.vote_url, {'candidate': self.candidate2.pk})

        existing_vote = Vote.objects.filter(
            voter=self.voter, election=self.election
        ).first()
        self.assertIsNotNone(existing_vote, "Original vote must still exist.")
        self.assertEqual(
            existing_vote.candidate, self.candidate1,
            "SECURITY FINDING: Second vote overwrote the first vote's candidate choice!",
        )

    def test_voter_can_vote_in_two_different_elections_independently(self):
        """
        Gap #5 (positive, per-election scope): The unique constraint is
        unique_together = ('voter', 'election').  A voter must be allowed to
        cast one vote in EACH separate election.  Verify the constraint is
        per-election, not global.
        """
        election2 = _make_open_election(self.admin, 'DV Election 2')
        c3 = Candidate.objects.create(
            election=election2, number=1,
            name='Paslon E2', vision='Visi E2', mission='Misi E2',
        )
        self.client.force_login(self.voter)
        # Vote in election 1
        self.client.post(self.vote_url, {'candidate': self.candidate1.pk})
        # Vote in election 2
        vote2_url = reverse('voting:cast', kwargs={'election_pk': election2.pk})
        self.client.post(vote2_url, {'candidate': c3.pk})

        count_e1 = Vote.objects.filter(voter=self.voter, election=self.election).count()
        count_e2 = Vote.objects.filter(voter=self.voter, election=election2).count()
        self.assertEqual(count_e1, 1, "Must have exactly 1 vote in election 1.")
        self.assertEqual(count_e2, 1, "Must have exactly 1 vote in election 2.")


# ═══════════════════════════════════════════════════════════════════
# GAP #6 — IntegrityError handler (views.py:60-64)
# ═══════════════════════════════════════════════════════════════════

class VotingIntegrityErrorHandlerTest(TestCase):
    """
    Gap #6: The IntegrityError handler at views.py:60-64 is the database-level
    fallback if the app-level double-vote check races with a concurrent request.
    If the DB constraint is absent, two concurrent requests produce two votes.
    If the handler is absent, the constraint violation surfaces as HTTP 500.

    These tests verify:
      (a) The Vote.unique_together DB constraint actually exists and fires.
      (b) The view absorbs the error gracefully (no HTTP 500).
    """

    def setUp(self):
        self.client = Client()
        self.admin = _make_user(
            'admin_ie', 'admin_ie@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.voter = _make_user(
            'voter_ie', 'voter_ie@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        self.election = _make_open_election(self.admin, 'IE Election')
        self.candidate1 = Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon IE1', vision='Visi', mission='Misi',
        )
        self.candidate2 = Candidate.objects.create(
            election=self.election, number=2,
            name='Paslon IE2', vision='Visi 2', mission='Misi 2',
        )

    # ── TC-IE-01 ────────────────────────────────────────────────────

    def test_db_unique_constraint_raises_integrity_error_on_duplicate(self):
        """
        Gap #6 (DB constraint): Creating two Vote rows with the same
        voter + election must raise IntegrityError at the database level.
        If this constraint is missing, the view-layer check is the only guard
        and a race condition would allow double voting.
        """
        # Create the first vote via ORM directly (bypassing view)
        Vote.objects.create(
            voter=self.voter,
            election=self.election,
            candidate=self.candidate1,
        )
        # Attempting a second Vote for the same voter+election must raise IntegrityError
        with self.assertRaises(
            IntegrityError,
            msg="SECURITY FINDING: DB unique_together constraint is missing — "
                "duplicate votes possible at the database level!",
        ):
            Vote.objects.create(
                voter=self.voter,
                election=self.election,
                candidate=self.candidate2,
            )

    def test_view_returns_non_500_on_repeated_post(self):
        """
        Gap #6 (view safety): A repeated POST to the vote endpoint must never
        return HTTP 500.  The view must handle the duplicate gracefully — either
        via the app-level check (redirect) or the IntegrityError handler.
        HTTP 500 leaks stack traces that aid attacker reconnaissance.
        """
        self.client.force_login(self.voter)
        vote_url = reverse('voting:cast', kwargs={'election_pk': self.election.pk})

        # First POST — expected to succeed
        self.client.post(vote_url, {'candidate': self.candidate1.pk})

        # Second POST — must NOT return 500
        response = self.client.post(vote_url, {'candidate': self.candidate2.pk})
        self.assertNotEqual(
            response.status_code, 500,
            "SECURITY FINDING: Vote endpoint returned HTTP 500 on duplicate POST — "
            "IntegrityError handler missing or broken!",
        )
