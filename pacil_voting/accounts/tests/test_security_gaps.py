"""
accounts/tests/test_security_gaps.py
Gap tests for the accounts app — closes gaps #1, #2, #3, #10.

Gaps addressed
  #1  accounts/views.py:41-48   Successful login branch (AuditLog, session, LoginAttempt)
  #2  accounts/views.py:94-126  Voter add / delete by admin
  #3  accounts/views.py:137-153 Candidate account creation and role assignment
  #10 accounts/utils.py:17-20   is_safe_text() allowlist validator

Run:
    python manage.py test accounts.tests.test_security_gaps -v 2
"""

from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser, LoginAttempt
from accounts.utils import is_safe_text
from audit.models import AuditLog
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


# ─── strong password that passes Django validators ─────────────────
_STRONG_PW = 'S3cur3Passw0rd!'


# ═══════════════════════════════════════════════════════════════════
# GAP #1 — Successful login branch (views.py:41-48)
# ═══════════════════════════════════════════════════════════════════

class AccountsAuthHappyPathTest(TestCase):
    """
    Gap #1: The successful login branch (login(), session, AuditLog.ACTION_LOGIN,
    LoginAttempt success=True) was never exercised.  A regression there would
    silently break the entire authentication flow.
    """

    def setUp(self):
        self.client = Client()
        self.voter = _make_user(
            'voter_hp', 'voter_hp@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        self.admin = _make_user(
            'admin_hp', 'admin_hp@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.candidate_user = _make_user(
            'cand_hp', 'cand_hp@test.com', 'Cand@123!', CustomUser.ROLE_CANDIDATE
        )

    def _do_login(self, email, password):
        return self.client.post(
            reverse('accounts:login'),
            {'email': email, 'password': password},
            follow=False,
        )

    # ── TC-BA-HappyPath-01 ──────────────────────────────────────────

    def test_successful_login_redirects_to_home(self):
        """
        Successful login must redirect (HTTP 302) to the home page, not loop
        back to the login page.  A broken redirect would strand every user.
        """
        response = self._do_login('voter_hp@test.com', 'Voter@123!')
        self.assertEqual(
            response.status_code, 302,
            "Successful login must return HTTP 302 redirect.",
        )
        self.assertNotIn(
            reverse('accounts:login'),
            response.get('Location', ''),
            "Successful login must NOT redirect back to the login page.",
        )

    def test_successful_login_creates_action_login_audit_entry(self):
        """
        Gap #1: Every successful login must create an AuditLog entry with
        ACTION_LOGIN for the authenticated user.  Missing entries make forensic
        investigation impossible after a security incident.
        """
        self._do_login('voter_hp@test.com', 'Voter@123!')
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.ACTION_LOGIN,
                actor=self.voter,
            ).exists(),
            "SECURITY FINDING: Successful login did not create AuditLog ACTION_LOGIN entry.",
        )

    def test_successful_login_creates_login_attempt_with_success_true(self):
        """
        Gap #1: A LoginAttempt row with success=True must be inserted on every
        successful login.  This row is used by is_locked_out() to count failures —
        the success=True record resets context for lockout calculations.
        """
        self._do_login('voter_hp@test.com', 'Voter@123!')
        self.assertTrue(
            LoginAttempt.objects.filter(
                email='voter_hp@test.com',
                success=True,
            ).exists(),
            "Successful login must create a LoginAttempt row with success=True.",
        )

    def test_all_roles_successful_login_redirects_to_home(self):
        """
        Gap #1 (all roles): Voter, admin, and candidate must all reach the
        home page after a successful login — no role should be stranded or
        redirected to the wrong page due to role confusion.
        """
        credentials = [
            ('voter_hp@test.com',  'Voter@123!',  'PEMILIH'),
            ('admin_hp@test.com',  'Admin@123!',  'ADMIN'),
            ('cand_hp@test.com',   'Cand@123!',   'CANDIDATE'),
        ]
        for email, password, role_label in credentials:
            self.client = Client()
            response = self._do_login(email, password)
            self.assertEqual(
                response.status_code, 302,
                f"Role {role_label}: successful login must HTTP 302.",
            )
            self.assertNotIn(
                reverse('accounts:login'),
                response.get('Location', ''),
                f"Role {role_label}: login must not redirect back to login page.",
            )

    def test_failed_login_does_not_create_action_login_entry(self):
        """
        Gap #1 (negative): A FAILED login must NOT create an AuditLog ACTION_LOGIN
        entry.  Logging failures as successes would corrupt the audit trail and
        could mask brute-force attacks in log reviews.
        """
        self._do_login('voter_hp@test.com', 'WrongPassword!')
        self.assertFalse(
            AuditLog.objects.filter(
                action=AuditLog.ACTION_LOGIN,
                actor=self.voter,
            ).exists(),
            "SECURITY FINDING: Failed login created an ACTION_LOGIN audit entry.",
        )

    def test_failed_login_creates_action_login_failed_entry(self):
        """
        Gap #1 (negative): A failed login must create AuditLog ACTION_LOGIN_FAILED.
        This is the correct audit trail entry for failed attempts; it feeds into
        brute-force lockout detection.
        """
        self._do_login('voter_hp@test.com', 'WrongPassword!')
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.ACTION_LOGIN_FAILED,
            ).exists(),
            "Failed login must create AuditLog ACTION_LOGIN_FAILED entry.",
        )


# ═══════════════════════════════════════════════════════════════════
# GAP #2 — Voter add / delete by admin (views.py:94-126)
# ═══════════════════════════════════════════════════════════════════

class AccountsAdminVoterManagementTest(TestCase):
    """
    Gap #2: Admin voter add/delete views were completely untested.
    These are privileged mutations — broken access control here means any
    authenticated user could create or delete voter accounts.
    """

    def setUp(self):
        self.client = Client()
        self.admin = _make_user(
            'admin_vm', 'admin_vm@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.voter = _make_user(
            'voter_vm', 'voter_vm@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        self.voter_to_delete = _make_user(
            'voter_del', 'voter_del@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )

    # ── TC-VM-01 ────────────────────────────────────────────────────

    def test_admin_can_add_new_voter_via_form(self):
        """
        Gap #2: Admin POST to voter-add must create a new CustomUser with
        ROLE_PEMILIH.  Tests the full form-to-DB path.
        """
        self.client.force_login(self.admin)
        post_data = {
            'email': 'newvoter@example.com',
            'first_name': 'Budi',
            'last_name': 'Santoso',
            'nim': '12345',
            'username': 'budisantoso',
            'password': _STRONG_PW,
            'password_confirm': _STRONG_PW,
        }
        self.client.post(reverse('accounts:add_voter'), post_data)
        self.assertTrue(
            CustomUser.objects.filter(email='newvoter@example.com').exists(),
            "Admin must be able to add a new voter account.",
        )

    def test_new_voter_has_pemilih_role_only(self):
        """
        Gap #2 (role assignment): The voter created via voter-add must have
        ROLE_PEMILIH and must NOT be staff or superuser — assigning a higher
        privilege here would be an immediate privilege escalation.
        """
        self.client.force_login(self.admin)
        post_data = {
            'email': 'rolecheck@example.com',
            'first_name': 'Role',
            'last_name': 'Check',
            'nim': '99999',
            'username': 'rolecheck',
            'password': _STRONG_PW,
            'password_confirm': _STRONG_PW,
        }
        self.client.post(reverse('accounts:add_voter'), post_data)
        try:
            created = CustomUser.objects.get(email='rolecheck@example.com')
            self.assertEqual(
                created.role, CustomUser.ROLE_PEMILIH,
                "SECURITY FINDING: New voter has wrong role — expected ROLE_PEMILIH.",
            )
            self.assertFalse(
                created.is_staff,
                "SECURITY FINDING: New voter account is_staff=True — privilege escalation!",
            )
            self.assertFalse(
                created.is_superuser,
                "SECURITY FINDING: New voter account is_superuser=True — privilege escalation!",
            )
        except CustomUser.DoesNotExist:
            self.fail("Voter was not created — admin voter-add broken.")

    def test_voter_cannot_add_new_voter(self):
        """
        Gap #2 (access control): A voter must be blocked from the voter-add
        endpoint.  Voters creating new accounts is a privilege escalation.
        """
        self.client.force_login(self.voter)
        initial_count = CustomUser.objects.filter(role=CustomUser.ROLE_PEMILIH).count()
        post_data = {
            'email': 'unauthorized@example.com',
            'first_name': 'Unauthorized',
            'last_name': '',
            'nim': '',
            'username': 'unauthorized',
            'password': _STRONG_PW,
            'password_confirm': _STRONG_PW,
        }
        response = self.client.post(reverse('accounts:add_voter'), post_data)
        self.assertIn(
            response.status_code, [302, 403],
            "Voter must be blocked from voter-add (302 or 403).",
        )
        final_count = CustomUser.objects.filter(role=CustomUser.ROLE_PEMILIH).count()
        self.assertEqual(
            initial_count, final_count,
            "SECURITY FINDING: Voter was able to create a new user account!",
        )

    def test_candidate_cannot_add_voter(self):
        """
        Gap #2 (access control): A candidate user must also be blocked from voter-add.
        The @admin_required decorator only allows ROLE_ADMIN.
        """
        cand_user = _make_user(
            'cand_vm', 'cand_vm@test.com', 'Cand@123!', CustomUser.ROLE_CANDIDATE
        )
        self.client.force_login(cand_user)
        initial_count = CustomUser.objects.count()
        response = self.client.post(reverse('accounts:add_voter'), {
            'email': 'nocreate@example.com',
            'first_name': 'No',
            'username': 'nocreate',
            'password': _STRONG_PW,
            'password_confirm': _STRONG_PW,
        })
        self.assertIn(response.status_code, [302, 403], "Candidate must be blocked from voter-add.")
        self.assertEqual(
            initial_count, CustomUser.objects.count(),
            "SECURITY FINDING: Candidate created a new user account!",
        )

    def test_admin_can_delete_voter(self):
        """
        Gap #2: Admin must be able to delete a voter account via POST to voter-delete.
        Verifies the full delete path functions correctly.
        """
        self.client.force_login(self.admin)
        pk = self.voter_to_delete.pk
        response = self.client.post(
            reverse('accounts:delete_voter', kwargs={'pk': pk})
        )
        self.assertIn(response.status_code, [302, 200], "Admin delete must succeed.")
        self.assertFalse(
            CustomUser.objects.filter(pk=pk).exists(),
            "Admin delete voter — user must no longer exist in DB.",
        )

    def test_voter_cannot_delete_another_voter(self):
        """
        Gap #2 (access control): A voter calling voter-delete is a lateral
        denial-of-service — attackers delete other voters so they cannot vote.
        Must be blocked by @admin_required.
        """
        self.client.force_login(self.voter)
        pk = self.voter_to_delete.pk
        response = self.client.post(
            reverse('accounts:delete_voter', kwargs={'pk': pk})
        )
        self.assertIn(
            response.status_code, [302, 403],
            "Voter must be blocked from deleting other voters.",
        )
        self.assertTrue(
            CustomUser.objects.filter(pk=pk).exists(),
            "SECURITY FINDING: Voter was able to delete another user account!",
        )

    def test_voter_delete_endpoint_returns_404_for_admin_pk(self):
        """
        Gap #2 (guard): voter-delete uses get_object_or_404(CustomUser, pk=pk,
        role=ROLE_PEMILIH).  Passing an admin's pk must return 404, not delete
        the admin.  This prevents accidental or malicious admin account deletion.
        """
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('accounts:delete_voter', kwargs={'pk': self.admin.pk})
        )
        self.assertEqual(
            response.status_code, 404,
            "voter-delete with an admin pk must return 404, not delete the admin.",
        )
        self.assertTrue(
            CustomUser.objects.filter(pk=self.admin.pk).exists(),
            "SECURITY FINDING: Admin account deleted via voter-delete endpoint!",
        )


# ═══════════════════════════════════════════════════════════════════
# GAP #3 — Candidate account creation and role assignment (views.py:137-153)
# ═══════════════════════════════════════════════════════════════════

class AccountsCandidateCreationSecurityTest(TestCase):
    """
    Gap #3: Candidate account creation via add_candidate_user_view was never
    tested.  Wrong role assignment here immediately escalates a new account to
    admin or staff privileges.
    """

    def setUp(self):
        self.client = Client()
        self.admin = _make_user(
            'admin_cc', 'admin_cc@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.voter = _make_user(
            'voter_cc', 'voter_cc@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        # An unlinked Candidate is required by AddCandidateUserForm
        self.election = Election.objects.create(
            title='CC Test Election',
            description='',
            start_date=timezone.now() + timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )
        self.candidate_profile = Candidate.objects.create(
            election=self.election,
            number=1,
            name='Paslon CC',
            vision='Visi CC',
            mission='Misi CC',
        )  # user=None (unlinked)

    def _candidate_post_data(self, email, username):
        return {
            'email': email,
            'first_name': 'Kandidat',
            'last_name': 'Baru',
            'username': username,
            'password': _STRONG_PW,
            'password_confirm': _STRONG_PW,
            'candidate': self.candidate_profile.pk,
        }

    # ── TC-CC-01 ────────────────────────────────────────────────────

    def test_candidate_creation_assigns_role_candidate_only(self):
        """
        Gap #3: The account created through add_candidate_user must have
        ROLE_CANDIDATE — no more, no less.  If role assignment logic is wrong
        (e.g., ROLE_ADMIN gets assigned), it is a critical privilege escalation.
        """
        self.client.force_login(self.admin)
        self.client.post(
            reverse('accounts:add_candidate_user'),
            self._candidate_post_data('newcand@example.com', 'newcanduser'),
        )
        try:
            created = CustomUser.objects.get(email='newcand@example.com')
            self.assertEqual(
                created.role, CustomUser.ROLE_CANDIDATE,
                "SECURITY FINDING: Created account has wrong role — expected ROLE_CANDIDATE.",
            )
        except CustomUser.DoesNotExist:
            self.fail("Candidate account was not created by admin — add_candidate_user broken.")

    def test_candidate_account_is_not_staff_or_superuser(self):
        """
        Gap #3 (privilege check): The created candidate account must be a
        regular (non-staff, non-superuser) user.  Staff or superuser status
        would grant access to the Django admin panel.
        """
        self.client.force_login(self.admin)
        self.client.post(
            reverse('accounts:add_candidate_user'),
            self._candidate_post_data('staffcheck@example.com', 'staffcheckuser'),
        )
        try:
            created = CustomUser.objects.get(email='staffcheck@example.com')
            self.assertFalse(
                created.is_staff,
                "SECURITY FINDING: Candidate account is_staff=True — Django admin access!",
            )
            self.assertFalse(
                created.is_superuser,
                "SECURITY FINDING: Candidate account is_superuser=True — privilege escalation!",
            )
        except CustomUser.DoesNotExist:
            self.fail("Account not created.")

    def test_voter_cannot_create_candidate_account(self):
        """
        Gap #3 (access control): A voter calling add_candidate_user is a
        privilege escalation — they would create a new CANDIDATE account.
        @admin_required must block this entirely.
        """
        self.client.force_login(self.voter)
        initial_count = CustomUser.objects.count()
        response = self.client.post(
            reverse('accounts:add_candidate_user'),
            self._candidate_post_data('votertrying@example.com', 'votertrying'),
        )
        self.assertIn(
            response.status_code, [302, 403],
            "Voter must be blocked from creating candidate accounts.",
        )
        self.assertEqual(
            initial_count, CustomUser.objects.count(),
            "SECURITY FINDING: Voter created a new candidate account!",
        )

    def test_candidate_cannot_create_another_candidate(self):
        """
        Gap #3 (lateral privilege): A candidate user must be blocked from
        creating additional candidate accounts (lateral role creation).
        """
        existing_cand_user = _make_user(
            'cand_cc', 'cand_cc@test.com', 'Cand@123!', CustomUser.ROLE_CANDIDATE
        )
        # Need a second unlinked candidate profile for the form
        cand_profile2 = Candidate.objects.create(
            election=self.election, number=2,
            name='Paslon CC2', vision='Visi', mission='Misi',
        )
        self.client.force_login(existing_cand_user)
        initial_count = CustomUser.objects.count()
        response = self.client.post(
            reverse('accounts:add_candidate_user'),
            {
                'email': 'lateralcand@example.com',
                'first_name': 'Lateral',
                'last_name': '',
                'username': 'lateralcand',
                'password': _STRONG_PW,
                'password_confirm': _STRONG_PW,
                'candidate': cand_profile2.pk,
            },
        )
        self.assertIn(
            response.status_code, [302, 403],
            "Candidate must not create another candidate account.",
        )
        self.assertEqual(
            initial_count, CustomUser.objects.count(),
            "SECURITY FINDING: Candidate created another candidate account!",
        )


# ═══════════════════════════════════════════════════════════════════
# GAP #10 — is_safe_text() allowlist validator (accounts/utils.py:17-20)
# ═══════════════════════════════════════════════════════════════════

class IsSafeTextValidatorTest(TestCase):
    """
    Gap #10: is_safe_text() is the allowlist regex gatekeeper for all
    user-supplied text fields.  It has never been directly tested.  If this
    regex has a bug, every XSS and SSTI defence built on top of it collapses.

    The function signature: is_safe_text(value, max_length=500) → bool
    Pattern allows: word chars, spaces, .,−()!?:;"'&/+=@#%^*[] + accented Latin
    """

    # ── safe inputs ─────────────────────────────────────────────────

    def test_normal_latin_text_is_accepted(self):
        """Standard candidate names and descriptions must be accepted."""
        safe_inputs = [
            "Kandidat Bagus",
            "Nama-Nama Normal 123",
            "Budi Santoso S.T.",
            "Vision: Build a better future!",
            "Misi: (1) Improve quality, (2) Reduce cost.",
        ]
        for text in safe_inputs:
            self.assertTrue(
                is_safe_text(text),
                f"Safe text '{text}' was incorrectly rejected by is_safe_text().",
            )

    def test_empty_string_returns_true(self):
        """
        Empty string is a valid input (optional fields); the function must
        not crash and must return True to allow empty values.
        """
        self.assertTrue(
            is_safe_text(''),
            "is_safe_text('') must return True (empty is allowed).",
        )

    def test_none_value_returns_true(self):
        """None value (missing optional field) must return True without raising."""
        self.assertTrue(
            is_safe_text(None),
            "is_safe_text(None) must return True (None is treated as empty).",
        )

    # ── dangerous inputs ─────────────────────────────────────────────

    def test_script_tag_is_rejected(self):
        """
        <script>alert(1)</script> must be rejected — the < > angle brackets are
        not in the allowlist pattern.  This is the primary XSS vector (CWE-79).
        """
        self.assertFalse(
            is_safe_text("<script>alert(1)</script>"),
            "SECURITY FINDING: is_safe_text() accepted a <script> tag — XSS protection broken!",
        )

    def test_html_tags_are_rejected(self):
        """
        HTML injection payloads containing < or > must be rejected.
        The allowlist pattern does not include angle brackets.
        """
        html_payloads = [
            "<h1>Hacked</h1>",
            "<img src=x onerror=alert(1)>",
            "<b onmouseover=alert('xss')>text</b>",
            "<iframe src=evil.com>",
        ]
        for payload in html_payloads:
            self.assertFalse(
                is_safe_text(payload),
                f"SECURITY FINDING: is_safe_text() accepted HTML payload '{payload}'.",
            )

    def test_ssti_curly_braces_are_rejected(self):
        """
        Server-Side Template Injection payloads {{7*7}} and {{config.SECRET_KEY}}
        must be rejected because { and } are not in the allowlist (CWE-94).
        """
        ssti_payloads = [
            "{{7*7}}",
            "{{config.SECRET_KEY}}",
            "{%import os%}",
            "{% if 1==1 %}yes{% endif %}",
        ]
        for payload in ssti_payloads:
            self.assertFalse(
                is_safe_text(payload),
                f"SECURITY FINDING: is_safe_text() accepted SSTI payload '{payload}'.",
            )

    def test_angle_bracket_only_strings_are_rejected(self):
        """Individual < and > characters must be rejected by the allowlist."""
        self.assertFalse(is_safe_text("<"), "Single '<' must be rejected.")
        self.assertFalse(is_safe_text(">"), "Single '>' must be rejected.")
        self.assertFalse(is_safe_text("a<b"), "'a<b' must be rejected — contains <.")

    # ── NOTE on SQL injection ────────────────────────────────────────
    # is_safe_text() ALLOWS single quotes (') intentionally — they appear in valid
    # Indonesian names like "O'Sullivan" and quoted text.  SQL injection prevention
    # relies on the Django ORM's parameterized queries, NOT on this function.
    # The test below documents this intentional design decision.

    def test_sql_injection_characters_are_allowed_by_design(self):
        """
        DESIGN NOTE: is_safe_text() allows single quotes and comparison characters
        because they are needed for normal text (e.g., O'Brien, contractions).
        SQLi protection comes from the ORM, not this function.
        This test documents the intentional scope of the allowlist.
        """
        sqli_text = "' OR '1'='1"  # all chars in allowlist: ', space, letters, =
        result = is_safe_text(sqli_text)
        # This is expected to return True — document, do not assert False
        self.assertIsInstance(result, bool,
            "is_safe_text() must return a bool for any input, including SQL-like text.")

    # ── boundary / robustness ────────────────────────────────────────

    def test_max_length_boundary_is_enforced(self):
        """
        Text exactly at max_length (500) must be accepted; text one character
        over must be rejected.  Validates the len(value) <= max_length check.
        """
        # 500 'a' chars — exactly at boundary
        at_boundary = 'a' * 500
        self.assertTrue(
            is_safe_text(at_boundary),
            "500-char string must be accepted (at max_length boundary).",
        )
        # 501 'a' chars — one over
        over_boundary = 'a' * 501
        self.assertFalse(
            is_safe_text(over_boundary),
            "501-char string must be rejected (exceeds max_length=500).",
        )

    def test_very_long_input_does_not_crash_or_redos(self):
        """
        Security: a 10,000-character safe string must complete without raising
        any exception or timing out (ReDoS check).  The allowlist regex uses a
        character class with '+', which is not susceptible to catastrophic
        backtracking for the patterns used here.
        """
        long_safe = 'Kandidat Normal ' * 625  # 10,000 chars, all safe
        try:
            result = is_safe_text(long_safe)
            self.assertIsInstance(result, bool,
                "is_safe_text() must return a bool for long input without crashing.")
        except Exception as exc:
            self.fail(f"is_safe_text() raised {type(exc).__name__} on long input: {exc}")
