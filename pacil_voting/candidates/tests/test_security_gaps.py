"""
candidates/tests/test_security_gaps.py
Gap tests for the candidates app — closes gaps #8 and #9.

Gaps addressed
  #8  candidates/views.py:16-92    Add / edit / delete guards on non-DRAFT elections
  #9  candidates/views.py:99-129   Candidate self-edit lock during OPEN election

Run:
    python manage.py test candidates.tests.test_security_gaps -v 2
"""

from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from elections.models import Election
from candidates.models import Candidate


# ─── shared helpers ───────────────────────────────────────────────

def _make_user(username, email, password, role):
    user = CustomUser.objects.create_user(
        username=username, email=email, password=password,
    )
    user.role = role
    user.save()
    return user


def _make_election(admin, status=Election.STATUS_DRAFT, title='Test Election'):
    return Election.objects.create(
        title=title,
        description='',
        start_date=timezone.now() - timedelta(hours=1),
        end_date=timezone.now() + timedelta(hours=1),
        status=status,
        created_by=admin,
    )


def _make_candidate(election, number=1, name='Paslon Test'):
    return Candidate.objects.create(
        election=election, number=number,
        name=name,
        vision=f'Visi {name}',
        mission=f'Misi {name}',
    )


# ═══════════════════════════════════════════════════════════════════
# GAP #8 — Candidate mutation guards (views.py:16-92)
# ═══════════════════════════════════════════════════════════════════

class CandidateMutationGuardTest(TestCase):
    """
    Gap #8: The guards preventing add/edit/delete on non-DRAFT elections were
    never triggered by any test.  If broken:
      • Adding to a live election changes the ballot mid-vote.
      • Deleting from a live election invalidates existing votes.
    All three endpoints check election.status == STATUS_DRAFT before mutating.
    """

    def setUp(self):
        self.client = Client()
        self.admin = _make_user(
            'admin_cg', 'admin_cg@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.voter = _make_user(
            'voter_cg', 'voter_cg@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )

        # DRAFT election used for positive tests and mutation-guard negative tests
        self.draft_election = _make_election(self.admin, Election.STATUS_DRAFT, 'Draft Election')
        self.draft_candidate = _make_candidate(self.draft_election, number=1, name='Draft Paslon')

    # ── TC-CG-01: Add guards ──────────────────────────────────────────

    def test_cannot_add_candidate_to_open_election(self):
        """
        Gap #8: Adding a candidate to an OPEN election changes the ballot
        while voters are actively choosing.  Must be blocked.
        """
        open_election = _make_election(self.admin, Election.STATUS_OPEN, 'OPEN Election')
        initial_count = Candidate.objects.filter(election=open_election).count()
        self.client.force_login(self.admin)
        self.client.post(
            reverse('candidates:create', kwargs={'election_pk': open_election.pk}),
            {'number': 1, 'name': 'Illegal Candidate', 'vision': 'V', 'mission': 'M'},
        )
        final_count = Candidate.objects.filter(election=open_election).count()
        self.assertEqual(
            initial_count, final_count,
            "SECURITY FINDING: Candidate added to an OPEN election — ballot manipulation possible!",
        )

    def test_cannot_add_candidate_to_closed_election(self):
        """
        Gap #8: Closed elections are historical records.  No new candidates
        may be added post-closure.
        """
        closed_election = _make_election(self.admin, Election.STATUS_CLOSED, 'CLOSED Election')
        initial_count = Candidate.objects.filter(election=closed_election).count()
        self.client.force_login(self.admin)
        self.client.post(
            reverse('candidates:create', kwargs={'election_pk': closed_election.pk}),
            {'number': 1, 'name': 'Post-close Candidate', 'vision': 'V', 'mission': 'M'},
        )
        final_count = Candidate.objects.filter(election=closed_election).count()
        self.assertEqual(
            initial_count, final_count,
            "SECURITY FINDING: Candidate added to a CLOSED election!",
        )

    def test_can_add_candidate_to_draft_election(self):
        """
        Gap #8 (positive): Adding a candidate to a DRAFT election must succeed.
        Verifies the guard only blocks the wrong states.
        """
        draft_election = _make_election(self.admin, Election.STATUS_DRAFT, 'Draft for Add')
        initial_count = Candidate.objects.filter(election=draft_election).count()
        self.client.force_login(self.admin)
        self.client.post(
            reverse('candidates:create', kwargs={'election_pk': draft_election.pk}),
            {'number': 1, 'name': 'Valid Candidate', 'vision': 'Visi', 'mission': 'Misi'},
        )
        final_count = Candidate.objects.filter(election=draft_election).count()
        self.assertEqual(
            final_count, initial_count + 1,
            "Admin must be able to add a candidate to a DRAFT election.",
        )

    # ── TC-CG-02: Edit guards ─────────────────────────────────────────

    def test_cannot_edit_candidate_on_open_election(self):
        """
        Gap #8: Editing a candidate during a live election changes what voters
        see on the ballot.  Must be blocked once election is OPEN.
        """
        open_election = _make_election(self.admin, Election.STATUS_OPEN, 'OPEN for Edit Test')
        candidate = _make_candidate(open_election, name='Original Name')
        self.client.force_login(self.admin)
        self.client.post(
            reverse('candidates:edit', kwargs={'pk': candidate.pk}),
            {'number': 1, 'name': 'TAMPERED NAME', 'vision': 'V tampered', 'mission': 'M tampered'},
        )
        candidate.refresh_from_db()
        self.assertEqual(
            candidate.name, 'Original Name',
            "SECURITY FINDING: Candidate name changed on OPEN election — ballot manipulation!",
        )

    def test_cannot_edit_candidate_on_closed_election(self):
        """
        Gap #8: Editing candidates in a closed election retroactively alters
        the official record of who the voters chose between.
        """
        closed_election = _make_election(self.admin, Election.STATUS_CLOSED, 'CLOSED for Edit')
        candidate = _make_candidate(closed_election, name='Closed Candidate')
        self.client.force_login(self.admin)
        self.client.post(
            reverse('candidates:edit', kwargs={'pk': candidate.pk}),
            {'number': 1, 'name': 'RETROACTIVE EDIT', 'vision': 'V', 'mission': 'M'},
        )
        candidate.refresh_from_db()
        self.assertEqual(
            candidate.name, 'Closed Candidate',
            "SECURITY FINDING: Candidate edited in a CLOSED election!",
        )

    # ── TC-CG-03: Delete guards ───────────────────────────────────────

    def test_cannot_delete_candidate_on_open_election(self):
        """
        Gap #8: Deleting a candidate from a live election invalidates any
        existing votes for that candidate, corrupting the count.
        Must be blocked once election is OPEN.
        """
        open_election = _make_election(self.admin, Election.STATUS_OPEN, 'OPEN for Delete')
        candidate = _make_candidate(open_election, name='Live Candidate')
        pk = candidate.pk
        self.client.force_login(self.admin)
        self.client.post(reverse('candidates:delete', kwargs={'pk': pk}))
        self.assertTrue(
            Candidate.objects.filter(pk=pk).exists(),
            "SECURITY FINDING: Candidate deleted from an OPEN election — vote corruption possible!",
        )

    def test_cannot_delete_candidate_on_closed_election(self):
        """
        Gap #8: Candidates of a closed election are part of the immutable
        historical record.  Deletion must be blocked.
        """
        closed_election = _make_election(self.admin, Election.STATUS_CLOSED, 'CLOSED for Delete')
        candidate = _make_candidate(closed_election, name='Historical Candidate')
        pk = candidate.pk
        self.client.force_login(self.admin)
        self.client.post(reverse('candidates:delete', kwargs={'pk': pk}))
        self.assertTrue(
            Candidate.objects.filter(pk=pk).exists(),
            "SECURITY FINDING: Candidate deleted from a CLOSED election!",
        )

    def test_can_delete_candidate_from_draft_election(self):
        """
        Gap #8 (positive): Admin must be able to delete a candidate from a
        DRAFT election.  Verifies the guard only blocks the wrong states.
        """
        draft_election = _make_election(self.admin, Election.STATUS_DRAFT, 'Draft for Delete')
        candidate = _make_candidate(draft_election, name='To Be Deleted')
        pk = candidate.pk
        self.client.force_login(self.admin)
        self.client.post(reverse('candidates:delete', kwargs={'pk': pk}))
        self.assertFalse(
            Candidate.objects.filter(pk=pk).exists(),
            "Admin must be able to delete a candidate from a DRAFT election.",
        )

    # ── TC-CG-04: Access control ──────────────────────────────────────

    def test_voter_cannot_add_candidate(self):
        """
        Gap #8 (RBAC): A voter adding themselves as a candidate is a critical
        integrity failure.  @admin_required must block all voter mutations.
        """
        initial_count = Candidate.objects.filter(election=self.draft_election).count()
        self.client.force_login(self.voter)
        response = self.client.post(
            reverse('candidates:create', kwargs={'election_pk': self.draft_election.pk}),
            {'number': 99, 'name': 'Voter Self-Candidate', 'vision': 'V', 'mission': 'M'},
        )
        self.assertIn(
            response.status_code, [302, 403],
            "Voter must be blocked from adding a candidate.",
        )
        final_count = Candidate.objects.filter(election=self.draft_election).count()
        self.assertEqual(
            initial_count, final_count,
            "SECURITY FINDING: Voter was able to add a candidate!",
        )

    def test_voter_cannot_delete_candidate(self):
        """
        Gap #8 (RBAC): A voter deleting a candidate is a targeted attack against
        a specific participant in the election.
        """
        pk = self.draft_candidate.pk
        self.client.force_login(self.voter)
        response = self.client.post(reverse('candidates:delete', kwargs={'pk': pk}))
        self.assertIn(
            response.status_code, [302, 403],
            "Voter must be blocked from deleting a candidate.",
        )
        self.assertTrue(
            Candidate.objects.filter(pk=pk).exists(),
            "SECURITY FINDING: Voter deleted a candidate!",
        )


# ═══════════════════════════════════════════════════════════════════
# GAP #9 — Candidate self-edit lock (views.py:99-129)
# ═══════════════════════════════════════════════════════════════════

class CandidateSelfEditLockTest(TestCase):
    """
    Gap #9: Candidates can edit their own profile (vision/mission) while the
    election is DRAFT.  Once the election is OPEN, edits must be locked.
    This lock was never tested.  A regression allows mid-election profile edits
    that could influence voters' decisions.

    The view (candidate_edit_profile_view) uses:
      locked = election.status != Election.STATUS_DRAFT
    """

    def setUp(self):
        self.client = Client()
        self.admin = _make_user(
            'admin_sl', 'admin_sl@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.cand_user_a = _make_user(
            'cand_sl_a', 'cand_sl_a@test.com', 'Cand@123!', CustomUser.ROLE_CANDIDATE
        )
        self.cand_user_b = _make_user(
            'cand_sl_b', 'cand_sl_b@test.com', 'Cand2@123!', CustomUser.ROLE_CANDIDATE
        )
        # DRAFT election for edit-allowed tests
        self.draft_election = _make_election(self.admin, Election.STATUS_DRAFT, 'SL Election')
        # Candidate A — linked to cand_user_a
        self.candidate_a = _make_candidate(self.draft_election, number=1, name='Paslon A')
        self.candidate_a.user = self.cand_user_a
        self.candidate_a.save()
        # Candidate B — linked to cand_user_b (used for cross-edit tests)
        self.candidate_b = _make_candidate(self.draft_election, number=2, name='Paslon B')
        self.candidate_b.user = self.cand_user_b
        self.candidate_b.save()

    # ── TC-SL-01 ────────────────────────────────────────────────────

    def test_candidate_can_edit_own_profile_on_draft_election(self):
        """
        Gap #9 (positive): Self-edit is allowed while election is DRAFT.
        The view sets locked=False and processes the CandidateProfileForm.
        """
        self.client.force_login(self.cand_user_a)
        response = self.client.post(
            reverse('candidates:my_profile'),
            {'vision': 'Updated Vision', 'mission': 'Updated Mission'},
        )
        self.candidate_a.refresh_from_db()
        self.assertIn(
            response.status_code, [302, 200],
            "Candidate self-edit on DRAFT election must be accepted.",
        )
        # Note: CandidateProfileForm.clean_vision() runs sanitize_text() which
        # html.escape()-escapes the input before saving.  Check with escape applied.
        import html as html_lib
        expected_vision = html_lib.escape('Updated Vision')
        self.assertEqual(
            self.candidate_a.vision, expected_vision,
            "Candidate vision must be updated after a DRAFT-election self-edit.",
        )

    def test_candidate_cannot_edit_own_profile_on_open_election(self):
        """
        Gap #9: Once the election is OPEN, candidate self-edit must be locked.
        The view checks locked = election.status != STATUS_DRAFT; if locked,
        any POST is rejected and the profile data must remain unchanged.
        """
        # Open the election
        self.draft_election.status = Election.STATUS_OPEN
        self.draft_election.save()

        original_vision = self.candidate_a.vision
        self.client.force_login(self.cand_user_a)
        response = self.client.post(
            reverse('candidates:my_profile'),
            {'vision': 'Mid-election Vision Change', 'mission': 'Mid-election Mission'},
        )
        self.candidate_a.refresh_from_db()
        self.assertEqual(
            self.candidate_a.vision, original_vision,
            "SECURITY FINDING: Candidate vision changed during OPEN election — "
            "self-edit lock broken! Mid-election manipulation is possible.",
        )

    def test_candidate_cannot_edit_own_profile_on_closed_election(self):
        """
        Gap #9: CLOSED elections are immutable.  Self-edit must be locked for
        CLOSED elections (locked = status != STATUS_DRAFT → True for CLOSED).
        """
        self.draft_election.status = Election.STATUS_CLOSED
        self.draft_election.save()

        original_vision = self.candidate_a.vision
        self.client.force_login(self.cand_user_a)
        self.client.post(
            reverse('candidates:my_profile'),
            {'vision': 'Post-close Edit Attempt', 'mission': 'Post-close Mission'},
        )
        self.candidate_a.refresh_from_db()
        self.assertEqual(
            self.candidate_a.vision, original_vision,
            "SECURITY FINDING: Candidate vision changed on CLOSED election — "
            "self-edit lock broken for CLOSED status!",
        )

    def test_candidate_self_edit_does_not_affect_other_candidate(self):
        """
        Gap #9 (horizontal isolation): candidate_edit_profile_view uses
        request.user.candidate_profile — it is bound to the authenticated user,
        not a user-supplied pk.  Candidate A's POST must NEVER change Candidate B.
        """
        original_b_vision = self.candidate_b.vision
        self.client.force_login(self.cand_user_a)
        self.client.post(
            reverse('candidates:my_profile'),
            {'vision': 'A edits their own profile', 'mission': 'A mission'},
        )
        self.candidate_b.refresh_from_db()
        self.assertEqual(
            self.candidate_b.vision, original_b_vision,
            "SECURITY FINDING: Candidate A's self-edit changed Candidate B's profile — "
            "horizontal isolation broken!",
        )

    def test_voter_cannot_access_candidate_profile_edit(self):
        """
        Gap #9 (RBAC): @candidate_required blocks voters from the self-edit page.
        A voter reaching this endpoint could attempt to modify a candidate profile.
        """
        voter = _make_user(
            'voter_sl', 'voter_sl@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        self.client.force_login(voter)
        response = self.client.get(reverse('candidates:my_profile'))
        self.assertIn(
            response.status_code, [302, 403],
            "Voter must be blocked from the candidate self-edit profile page.",
        )

    def test_admin_can_edit_candidate_via_admin_edit_endpoint(self):
        """
        Gap #9: Admin uses candidates:edit (pk-based) to edit candidates
        while the election is DRAFT.  This is separate from the self-edit view.
        Verifies admin editing still works as expected.
        """
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('candidates:edit', kwargs={'pk': self.candidate_a.pk}),
            {
                'number': 1,
                'name': 'Admin Updated Paslon A',
                'vision': 'Admin Updated Vision',
                'mission': 'Admin Updated Mission',
            },
        )
        self.candidate_a.refresh_from_db()
        self.assertIn(
            response.status_code, [302, 200],
            "Admin edit on DRAFT election must succeed.",
        )
        import html as html_lib
        expected_name = html_lib.escape('Admin Updated Paslon A')
        self.assertEqual(
            self.candidate_a.name, expected_name,
            "Admin must be able to edit a candidate on a DRAFT election.",
        )
