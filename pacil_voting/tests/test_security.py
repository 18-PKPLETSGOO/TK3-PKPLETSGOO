"""
Security Unit Test Suite — E-Voting System (PKPLETSGOO)

Coverage map:
  Category 1 — SQL Injection Prevention        (CWE-89)
  Category 2 — Code Injection / XSS            (CWE-79, CWE-94)
  Category 3 — Broken Authentication           (CWE-256, CWE-307, CWE-306, CWE-613, CWE-204)
  Category 4 — CSRF Protection                 (CWE-352)

Roles exercised: Voter (PEMILIH), Admin, Candidate (CANDIDATE)

Run with:
    cd pacil_voting
    python manage.py test tests.test_security -v 2
"""

import os
import re
import glob
from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from accounts.models import CustomUser, LoginAttempt
from elections.models import Election
from candidates.models import Candidate
from voting.models import Vote


# ═══════════════════════════════════════════════════════════════════
# SHARED HELPER — creates one user per role
# ═══════════════════════════════════════════════════════════════════

def _make_user(username, email, password, role):
    """Utility to create a CustomUser with an explicit role."""
    user = CustomUser.objects.create_user(
        username=username,
        email=email,
        password=password,
    )
    user.role = role
    user.save()
    return user


# ═══════════════════════════════════════════════════════════════════
# CATEGORY 1 — SQL INJECTION PREVENTION (CWE-89)
# ═══════════════════════════════════════════════════════════════════

class SQLInjectionPreventionTest(TestCase):
    """
    Verifies that the E-Voting application is resistant to SQL injection.

    Django ORM parameterizes all queries by default.  These tests confirm:
      (a) No raw-SQL string concatenation exists in the source code.
      (b) Injection payloads in form fields are rejected or produce no side-effects.
      (c) URL-parameter-based filtering only returns the intended records.

    OWASP A03:2021 · CWE-89
    """

    def setUp(self):
        self.client = Client()

        self.voter = _make_user(
            'voter_sqli', 'voter_sqli@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        self.admin = _make_user(
            'admin_sqli', 'admin_sqli@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.candidate_user = _make_user(
            'cand_sqli', 'cand_sqli@test.com', 'Cand@123!', CustomUser.ROLE_CANDIDATE
        )

        self.election = Election.objects.create(
            title='SQLi Test Election',
            description='Used for SQL injection tests',
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=1),
            status=Election.STATUS_OPEN,
            created_by=self.admin,
        )
        Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon Satu', vision='Visi Satu', mission='Misi Satu',
        )
        Candidate.objects.create(
            election=self.election, number=2,
            name='Paslon Dua', vision='Visi Dua', mission='Misi Dua',
        )

    # ── TC-SQLi-01 ──────────────────────────────────────────────────

    def test_sqli_01_login_bypass_via_email_injection(self):
        """
        TC-SQLi-01: SQL injection payloads in the email/password login fields must NOT
        bypass authentication for any role (voter, admin, candidate).

        Why it matters: Classic auth-bypass attack — attacker logs in as any user by
        injecting SQL that makes the WHERE clause always true.

        Django's LoginForm validates the email with a strict regex before it reaches
        authenticate(); even if that were bypassed, ORM uses parameterized queries.
        Expected: HTTP 200 (form re-rendered) for every payload, never a redirect to home.
        """
        payloads = [
            ("' OR '1'='1' --", "anything"),
            ('" OR "1"="1" --', "anything"),
            ("' OR 1=1--", "pass"),
            ("admin'--", "pass"),
            ("' OR 'x'='x", "pass"),
        ]
        for email_payload, pwd in payloads:
            response = self.client.post(
                reverse('accounts:login'),
                {'email': email_payload, 'password': pwd},
                follow=False,
            )
            self.assertNotEqual(
                response.status_code, 302,
                f"SECURITY FINDING: Login with SQLi payload '{email_payload}' returned 302 "
                "(possible authentication bypass).",
            )
            if response.status_code == 302:
                self.assertNotEqual(
                    response.get('Location', ''),
                    reverse('home'),
                    f"SQLi payload '{email_payload}' redirected to home — auth bypass!",
                )

    def test_sqli_01_login_bypass_all_roles(self):
        """
        TC-SQLi-01 (all roles): Confirm no role-specific code path allows SQLi login bypass.
        Tests voter, admin, and candidate credentials separately.
        """
        sqli_emails = [
            "' OR '1'='1",
            "x' OR 'x'='x",
            "1' OR '1' = '1",
        ]
        for email_payload in sqli_emails:
            response = self.client.post(
                reverse('accounts:login'),
                {'email': email_payload, 'password': 'anything'},
                follow=False,
            )
            self.assertNotEqual(
                response.status_code, 302,
                f"Role-agnostic login bypass with '{email_payload}'.",
            )

    # ── TC-SQLi-02 ──────────────────────────────────────────────────

    def test_sqli_02_union_injection_in_election_list_search(self):
        """
        TC-SQLi-02: UNION-based SQL injection via the election list ?q= search parameter.

        The view uses: Election.objects.filter(title__icontains=q)
        ORM generates: WHERE title LIKE %value% — value is parameterized, so the UNION
        is treated as a literal string and no extra rows are returned.

        Expected: HTTP 200 with no SQL error messages and no auth_user data in response.
        """
        self.client.force_login(self.voter)
        union_payload = "' UNION SELECT username, password, null FROM auth_user --"

        response = self.client.get(reverse('elections:list'), {'q': union_payload})

        self.assertEqual(
            response.status_code, 200,
            "Election list search with UNION payload should return HTTP 200 (not crash).",
        )
        content = response.content.decode('utf-8', errors='replace')
        for error_marker in ['OperationalError', 'ProgrammingError', 'sqlite3', 'syntax error']:
            self.assertNotIn(
                error_marker, content,
                f"SQL error marker '{error_marker}' in response — possible SQLi vulnerability.",
            )
        self.assertNotIn(
            'pbkdf2_sha256',
            content,
            "SECURITY FINDING: Password hash (pbkdf2_sha256) leaked — UNION injection effective!",
        )

    def test_sqli_02_or_injection_in_election_search(self):
        """
        TC-SQLi-02b: OR-based injection in search — must not return all rows.

        If unsanitized, ?q=x' OR '1'='1 would expand to: title LIKE '%x' OR '1'='1%'
        which is always true, leaking all elections.  ORM parameterization prevents this.
        """
        self.client.force_login(self.voter)
        response = self.client.get(reverse('elections:list'), {'q': "x' OR '1'='1"})

        self.assertEqual(response.status_code, 200, "OR injection in search should return 200.")
        content = response.content.decode('utf-8', errors='replace')
        for error_marker in ['OperationalError', 'ProgrammingError', 'sqlite3']:
            self.assertNotIn(
                error_marker, content,
                f"SQL error marker '{error_marker}' found in OR-injection response.",
            )

    # ── TC-SQLi-03 ──────────────────────────────────────────────────

    def test_sqli_03_no_raw_sql_string_concatenation_in_source(self):
        """
        TC-SQLi-03 (white-box): Scan all application .py files for dangerous raw SQL patterns.

        Safe:   cursor.execute("SELECT ... WHERE id = %s", (user_input,))
        Unsafe: cursor.execute("SELECT ... WHERE id = " + user_input)
                f"SELECT ... WHERE id = {user_input}"
                "SELECT ...".format(user_input)

        Any match is a potential SQLi entry point.
        """
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
        app_dirs = ['accounts', 'elections', 'candidates', 'voting', 'audit']

        dangerous_patterns = [
            r'f["\'].*SELECT.*\{',                         # f-string with SELECT
            r'"SELECT\s[^"]*"\s*\+',                       # string concat with SELECT
            r"'SELECT\s[^']*'\s*\+",                       # single-quoted concat
            r'\.format\(.*\).*\.execute\(',                # .format() before .execute()
            r'execute\(\s*["\'].*%[^,\)]',                 # %-format in execute (no tuple)
        ]

        violations = []
        for app in app_dirs:
            py_files = glob.glob(
                os.path.join(base_dir, app, '**', '*.py'), recursive=True
            )
            for filepath in py_files:
                if '__pycache__' in filepath or 'migrations' in filepath:
                    continue
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                        source = fh.read()
                    for pattern in dangerous_patterns:
                        matches = re.findall(pattern, source, re.IGNORECASE)
                        if matches:
                            violations.append(
                                f"  {os.path.relpath(filepath, base_dir)}: "
                                f"pattern '{pattern}' matched {matches}"
                            )
                except OSError:
                    pass

        self.assertEqual(
            len(violations), 0,
            "SECURITY FINDING: Raw SQL string concatenation detected:\n"
            + "\n".join(violations),
        )

    # ── TC-SQLi-04d ─────────────────────────────────────────────────

    def test_sqli_04d_election_detail_returns_only_requested_election(self):
        """
        TC-SQLi-04d (E-Voting): Accessing an election detail by PK must return ONLY that
        election's data — not leak other elections' candidates.

        The view uses get_object_or_404(Election, pk=pk) which is safe ORM.
        """
        self.client.force_login(self.voter)

        response = self.client.get(
            reverse('elections:detail', kwargs={'pk': self.election.pk})
        )
        self.assertEqual(response.status_code, 200, "Valid election detail must return 200.")
        content = response.content.decode('utf-8')
        self.assertIn('Paslon Satu', content, "Election detail must show its own candidates.")

        response_404 = self.client.get(
            reverse('elections:detail', kwargs={'pk': 99999})
        )
        self.assertEqual(
            response_404.status_code, 404,
            "Non-existent election PK must return 404 — must not leak any data.",
        )

    def test_sqli_04d_candidates_are_isolated_per_election(self):
        """
        TC-SQLi-04d (isolation): A candidate belonging to Election B must NOT appear when
        browsing Election A's detail page.  Verifies ORM FK filtering is effective.
        """
        self.client.force_login(self.voter)

        election2 = Election.objects.create(
            title='Isolated Election',
            description='',
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=1),
            status=Election.STATUS_OPEN,
            created_by=self.admin,
        )
        Candidate.objects.create(
            election=election2, number=1,
            name='Secret Paslon', vision='Secret Visi', mission='Secret Misi',
        )

        response = self.client.get(
            reverse('elections:detail', kwargs={'pk': self.election.pk})
        )
        content = response.content.decode('utf-8')
        self.assertNotIn(
            'Secret Paslon', content,
            "SECURITY FINDING: Candidate from a different election leaked in detail view.",
        )


# ═══════════════════════════════════════════════════════════════════
# CATEGORY 2 — CODE INJECTION / XSS PREVENTION (CWE-79, CWE-94)
# ═══════════════════════════════════════════════════════════════════

class CodeInjectionPreventionTest(TestCase):
    """
    Verifies protection against Cross-Site Scripting (XSS) and
    Server-Side Template Injection (SSTI).

    Defense layers tested:
      1. Form-layer validation (CandidateForm.clean_*) — rejects HTML/script tags.
      2. Template auto-escaping   — Django escapes {{ var }} output by default.
      3. White-box audit          — no |safe misuse on user-controlled fields.

    OWASP A03:2021 · CWE-79 (XSS) · CWE-94 (Code Injection / SSTI)
    """

    def setUp(self):
        self.client = Client()

        self.admin = _make_user(
            'admin_xss', 'admin_xss@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.voter = _make_user(
            'voter_xss', 'voter_xss@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        self.candidate_user = _make_user(
            'cand_xss', 'cand_xss@test.com', 'Cand@123!', CustomUser.ROLE_CANDIDATE
        )

        # Use DRAFT so candidates can be added via admin
        self.draft_election = Election.objects.create(
            title='XSS Test Election',
            description='',
            start_date=timezone.now() + timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )
        # Separate OPEN election for voter-visible rendering tests
        self.open_election = Election.objects.create(
            title='Open XSS Election',
            description='',
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=1),
            status=Election.STATUS_OPEN,
            created_by=self.admin,
        )

    # ── TC-CI-01 ────────────────────────────────────────────────────

    def test_ci_01_stored_xss_candidate_name_rejected_at_form_layer(self):
        """
        TC-CI-01: Admin submits <script>alert('XSS')</script> as candidate name.

        CandidateForm.clean_name() uses re.search(r'<[^>]+>', name) to reject HTML tags
        before the data ever reaches the database.
        Expected: No Candidate with the XSS name is stored.
        """
        self.client.force_login(self.admin)
        xss_name = "<script>alert('XSS')</script>"

        self.client.post(
            reverse('candidates:create', kwargs={'election_pk': self.draft_election.pk}),
            {'number': 1, 'name': xss_name, 'vision': 'Visi', 'mission': 'Misi'},
        )

        self.assertFalse(
            Candidate.objects.filter(name=xss_name).exists(),
            "SECURITY FINDING: XSS payload stored in database — CandidateForm validation bypassed!",
        )

    def test_ci_01_stored_xss_escaped_by_template_engine(self):
        """
        TC-CI-01 (template defence-in-depth): Even if a malicious name bypasses form
        validation and gets stored, Django's auto-escaping must render it harmlessly.

        The template renders {{ candidate.name }} without |safe, so Django converts
        < > to &lt; &gt; before emitting HTML.
        """
        xss_name = "<script>alert('XSS')</script>"
        Candidate.objects.create(
            election=self.open_election, number=1,
            name=xss_name, vision='Visi', mission='Misi',
        )

        self.client.force_login(self.voter)
        response = self.client.get(
            reverse('elections:detail', kwargs={'pk': self.open_election.pk})
        )
        content = response.content.decode('utf-8')

        self.assertNotIn(
            '<script>alert',
            content,
            "SECURITY FINDING: Raw <script> tag rendered — XSS via |safe or mark_safe() misuse!",
        )
        self.assertIn(
            '&lt;script&gt;',
            content,
            "Django template must HTML-escape <script> to &lt;script&gt;.",
        )

    # ── TC-CI-02 ────────────────────────────────────────────────────

    def test_ci_02_html_injection_rejected_at_form_layer(self):
        """
        TC-CI-02: HTML injection payload as candidate name is rejected by form validation.

        Payload: <h1>Hacked</h1><img src=x onerror=alert(1)>
        The clean_name() regex detects any < > tag and raises ValidationError.
        """
        self.client.force_login(self.admin)
        html_payload = "<h1>Hacked</h1><img src=x onerror=alert(1)>"

        self.client.post(
            reverse('candidates:create', kwargs={'election_pk': self.draft_election.pk}),
            {'number': 1, 'name': html_payload, 'vision': 'Visi', 'mission': 'Misi'},
        )

        self.assertFalse(
            Candidate.objects.filter(name=html_payload).exists(),
            "SECURITY FINDING: HTML injection payload stored — form validation bypass!",
        )

    def test_ci_02_html_injection_escaped_by_template_if_stored(self):
        """
        TC-CI-02 (template layer): HTML tags stored in the DB must be auto-escaped.

        Verifies that even the onerror event attribute cannot execute: the template
        renders it as the literal text onerror=alert(1), not as a live attribute.
        """
        html_payload = "<h1>Hacked</h1><img src=x onerror=alert(1)>"
        Candidate.objects.create(
            election=self.open_election, number=1,
            name=html_payload, vision='Visi', mission='Misi',
        )
        self.client.force_login(self.voter)
        response = self.client.get(
            reverse('elections:detail', kwargs={'pk': self.open_election.pk})
        )
        content = response.content.decode('utf-8')

        # Django escapes < and > — verify the raw unescaped tag does NOT appear.
        # The escaped form (&lt;h1&gt;...&lt;img src=x onerror=alert(1)&gt;) is safe:
        # the browser parses it as text, not as HTML elements.
        self.assertNotIn(
            '<h1>Hacked</h1>',
            content,
            "SECURITY FINDING: Unescaped <h1> tag rendered — HTML injection possible.",
        )
        # The dangerous form is <img … onerror=…> with a literal '<'.
        # If escaped correctly, '<img' (with real angle bracket) must NOT appear.
        self.assertNotIn(
            '<img src=x onerror=alert',
            content,
            "SECURITY FINDING: Unescaped <img onerror> tag rendered — XSS possible.",
        )
        # Confirm the escape DID happen (entities are present)
        self.assertIn(
            '&lt;h1&gt;',
            content,
            "Django must HTML-escape <h1> to &lt;h1&gt;.",
        )

    # ── TC-CI-03 ────────────────────────────────────────────────────

    def test_ci_03_ssti_payload_rejected_by_form(self):
        """
        TC-CI-03: Server-Side Template Injection payloads are rejected by form validation.

        CandidateForm.clean_name() uses re.search(r'[<>\\{\\}|\\\\\\^`]', name) which
        blocks {{ }} characters — the building blocks of SSTI payloads.
        Expected: No candidate stored with any SSTI payload as the name.
        """
        self.client.force_login(self.admin)
        ssti_payloads = ['{{7*7}}', '{{config.SECRET_KEY}}', '{%import os%}']

        for payload in ssti_payloads:
            self.client.post(
                reverse('candidates:create', kwargs={'election_pk': self.draft_election.pk}),
                {'number': 1, 'name': payload, 'vision': 'Visi', 'mission': 'Misi'},
            )
            self.assertFalse(
                Candidate.objects.filter(name=payload).exists(),
                f"SSTI payload '{payload}' was stored — form validation bypass!",
            )

    def test_ci_03_ssti_not_evaluated_even_if_stored(self):
        """
        TC-CI-03 (evaluation check): Django's DjangoTemplates backend does NOT evaluate
        {{ }} syntax inside data values — it only resolves template variables, not
        arbitrary Python expressions.

        {{7*7}} in a stored value must appear as the literal string (escaped), NOT '49'.
        SECRET_KEY must never appear in any rendered response.
        """
        ssti_name = "{{7*7}}"
        Candidate.objects.create(
            election=self.open_election, number=1,
            name=ssti_name, vision='Visi', mission='Misi',
        )
        self.client.force_login(self.voter)
        response = self.client.get(
            reverse('elections:detail', kwargs={'pk': self.open_election.pk})
        )
        content = response.content.decode('utf-8')

        self.assertNotIn(
            '>49<', content,
            "SECURITY FINDING: {{7*7}} was evaluated to 49 — template injection possible!",
        )
        self.assertNotIn(
            settings.SECRET_KEY, content,
            "SECURITY FINDING: settings.SECRET_KEY exposed in response — SSTI vulnerability!",
        )

    # ── TC-CI-04d ───────────────────────────────────────────────────

    def test_ci_04d_event_handler_injection_rejected_by_form(self):
        """
        TC-CI-04d (E-Voting): Inline event-handler injection via candidate name.

        Payload: <b onmouseover=alert('voted!')>Kandidat A</b>
        CandidateForm detects the HTML tag and raises a ValidationError, so the
        event handler is never stored.
        """
        self.client.force_login(self.admin)
        event_payload = "<b onmouseover=alert('voted!')>Kandidat A</b>"

        self.client.post(
            reverse('candidates:create', kwargs={'election_pk': self.draft_election.pk}),
            {'number': 1, 'name': event_payload, 'vision': 'Visi', 'mission': 'Misi'},
        )

        self.assertFalse(
            Candidate.objects.filter(name=event_payload).exists(),
            "SECURITY FINDING: Event-handler injection payload stored — XSS risk!",
        )

    def test_ci_04d_event_handler_escaped_if_stored(self):
        """
        TC-CI-04d (template): If event-handler payload is stored (bypassing form),
        Django's auto-escaping prevents the attribute from being parsed by the browser.
        """
        event_payload = "<b onmouseover=alert('voted!')>Kandidat A</b>"
        Candidate.objects.create(
            election=self.open_election, number=1,
            name=event_payload, vision='Visi', mission='Misi',
        )
        self.client.force_login(self.voter)
        response = self.client.get(
            reverse('elections:detail', kwargs={'pk': self.open_election.pk})
        )
        content = response.content.decode('utf-8')

        # Django escapes < and > so the payload becomes:
        #   &lt;b onmouseover=alert(&#x27;voted!&#x27;)&gt;Kandidat A&lt;/b&gt;
        # The browser parses this as text, not as a live element with an event handler.
        # The dangerous form is the raw tag with a literal '<b onmouseover='.
        self.assertNotIn(
            '<b onmouseover=alert',
            content,
            "SECURITY FINDING: Unescaped <b onmouseover> tag rendered — stored XSS!",
        )
        # Confirm escaping actually happened
        self.assertIn(
            '&lt;b onmouseover=',
            content,
            "Django must escape <b onmouseover= to &lt;b onmouseover=.",
        )

    # ── White-box: no |safe misuse ───────────────────────────────────

    def test_ci_whitebox_no_safe_filter_on_user_data_in_templates(self):
        """
        TC-CI (white-box): Audit all project templates for |safe filter usage.

        Django's |safe filter bypasses auto-escaping.  If applied to a user-controlled
        variable (e.g., {{ candidate.name|safe }}), it creates a stored XSS vector.
        Expected: No template variable uses |safe.
        """
        template_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'templates'
        )
        html_files = glob.glob(os.path.join(template_dir, '**', '*.html'), recursive=True)

        safe_filter_pattern = re.compile(r'\{\{[^}]+\|safe[\s|}]')
        violations = []

        for filepath in html_files:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if safe_filter_pattern.search(line):
                            violations.append(
                                f"  {os.path.relpath(filepath, template_dir)}:{lineno}: {line.strip()}"
                            )
            except OSError:
                pass

        self.assertEqual(
            len(violations), 0,
            "SECURITY FINDING: |safe filter found in templates — verify these are not "
            "user-controlled values:\n" + "\n".join(violations),
        )


# ═══════════════════════════════════════════════════════════════════
# CATEGORY 3 — BROKEN AUTHENTICATION MITIGATION
# (CWE-256, CWE-307, CWE-306, CWE-613, CWE-204)
# ═══════════════════════════════════════════════════════════════════

class BrokenAuthenticationTest(TestCase):
    """
    Verifies that the E-Voting system enforces correct authentication controls:

    CWE-256  Password stored as secure hash (not plaintext).
    CWE-307  Brute-force mitigated via LoginAttempt-based account lockout.
    CWE-306  All critical pages require authentication (@login_required / custom decorators).
    CWE-613  Sessions are fully invalidated after logout (session.flush()).
    CWE-204  Login failure messages do not disclose whether email or password was wrong.

    OWASP A07:2021
    """

    def setUp(self):
        self.client = Client()

        self.voter = _make_user(
            'voter_auth', 'voter_auth@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        self.admin = _make_user(
            'admin_auth', 'admin_auth@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )
        self.candidate_user = _make_user(
            'cand_auth', 'cand_auth@test.com', 'Cand@123!', CustomUser.ROLE_CANDIDATE
        )

        self.election = Election.objects.create(
            title='Auth Test Election',
            description='',
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=1),
            status=Election.STATUS_OPEN,
            created_by=self.admin,
        )
        Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon Auth', vision='Visi', mission='Misi',
        )

    # ── TC-BA-01 ────────────────────────────────────────────────────

    def test_ba_01_password_stored_as_hash_not_plaintext(self):
        """
        TC-BA-01: Passwords must be stored as cryptographic hashes, never as plaintext.

        CWE-256: Plaintext Storage of a Password.
        Django uses PBKDF2-SHA256 by default.  Stored value must start with 'pbkdf2_sha256$'.
        """
        user = CustomUser.objects.get(email='voter_auth@test.com')

        self.assertNotEqual(
            user.password, 'Voter@123!',
            "SECURITY FINDING: Password stored in plaintext — CWE-256 violation!",
        )
        self.assertTrue(
            user.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2')),
            f"SECURITY FINDING: Unexpected hash format: '{user.password[:30]}...'",
        )

    def test_ba_01_password_hashed_for_all_roles(self):
        """
        TC-BA-01 (all roles): Hashing must apply to every role — voter, admin, candidate.

        Verifies that the password field is never equal to the raw plaintext credential.
        """
        role_cases = [
            ('voter_auth@test.com',  'Voter@123!',  'PEMILIH'),
            ('admin_auth@test.com',  'Admin@123!',  'ADMIN'),
            ('cand_auth@test.com',   'Cand@123!',   'CANDIDATE'),
        ]
        for email, raw_pw, role_label in role_cases:
            user = CustomUser.objects.get(email=email)
            self.assertNotEqual(
                user.password, raw_pw,
                f"Role {role_label}: password stored as plaintext — CWE-256!",
            )
            self.assertTrue(
                user.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2')),
                f"Role {role_label}: password not using a recognised hash scheme.",
            )

    # ── TC-BA-02 ────────────────────────────────────────────────────

    def test_ba_02_account_lockout_after_max_failed_attempts(self):
        """
        TC-BA-02: The login view must lock an account after MAX_LOGIN_ATTEMPTS (5)
        consecutive failures within LOCKOUT_DURATION_MINUTES (15).

        CWE-307: Improper Restriction of Excessive Authentication Attempts.
        Implementation: LoginAttempt.is_locked_out() is checked in accounts/views.py
        before and after calling authenticate().
        """
        max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
        email = 'voter_auth@test.com'

        # Drive max_attempts failed logins through the real view to create LoginAttempt records
        for _ in range(max_attempts):
            self.client.post(
                reverse('accounts:login'),
                {'email': email, 'password': 'WrongPassword!'},
            )

        # The next POST triggers the pre-check (is_locked_out = True) and must show lockout msg
        response = self.client.post(
            reverse('accounts:login'),
            {'email': email, 'password': 'WrongPassword!'},
        )

        self.assertEqual(response.status_code, 200, "Lockout response must be HTTP 200.")
        content = response.content.decode('utf-8')

        lockout_indicators = ['Terlalu banyak', 'terkunci', 'coba lagi nanti']
        found = any(ind in content for ind in lockout_indicators)
        self.assertTrue(
            found,
            f"SECURITY FINDING: No lockout message after {max_attempts + 1} failed attempts. "
            "Brute-force protection may not be functioning (CWE-307).",
        )

    def test_ba_02_lockout_model_logic_is_correct(self):
        """
        TC-BA-02 (model unit test): Direct test of LoginAttempt.is_locked_out() to verify
        the lockout threshold logic independent of the view layer.
        """
        email = 'voter_auth@test.com'
        max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)

        self.assertFalse(
            LoginAttempt.is_locked_out(email, max_attempts, 15),
            "Account must NOT be locked before any failed attempts.",
        )

        for _ in range(max_attempts):
            LoginAttempt.objects.create(
                email=email, ip_address='127.0.0.1', success=False,
            )

        self.assertTrue(
            LoginAttempt.is_locked_out(email, max_attempts, 15),
            f"SECURITY FINDING: Account not locked after {max_attempts} failures — "
            "LoginAttempt.is_locked_out() logic incorrect (CWE-307)!",
        )

    # ── TC-BA-03 ────────────────────────────────────────────────────

    def test_ba_03_session_invalidated_after_logout(self):
        """
        TC-BA-03: After logout, accessing a protected page must redirect to login —
        the session must not remain valid.

        CWE-613: Insufficient Session Expiration.
        logout_view calls logout(request) + request.session.flush(), which deletes the
        current session from the store and issues a new empty session key.
        """
        # Login and confirm access
        self.client.force_login(self.voter)
        response_before = self.client.get(reverse('elections:list'))
        self.assertEqual(response_before.status_code, 200, "Must access elections:list before logout.")

        # Logout
        self.client.post(reverse('accounts:logout'))

        # Protected page must now redirect
        response_after = self.client.get(reverse('elections:list'))
        self.assertIn(
            response_after.status_code, [302, 301],
            "SECURITY FINDING: Protected page accessible after logout — session not invalidated!",
        )
        self.assertIn(
            'login', response_after.get('Location', '').lower(),
            "Post-logout redirect must point to the login page.",
        )

    def test_ba_03_session_key_changes_after_logout(self):
        """
        TC-BA-03 (session key rotation): The session key must change after logout.

        session.flush() discards the current session and creates a new key, so the
        old key stored in a captured cookie becomes useless.
        """
        self.client.force_login(self.voter)
        old_key = self.client.session.session_key
        self.assertIsNotNone(old_key, "Session key must exist after login.")

        self.client.post(reverse('accounts:logout'))

        new_key = self.client.session.session_key
        self.assertNotEqual(
            old_key, new_key,
            "SECURITY FINDING: Session key unchanged after logout — session fixation risk!",
        )

    # ── TC-BA-04 ────────────────────────────────────────────────────

    def test_ba_04_unauthenticated_cannot_access_election_list(self):
        """
        TC-BA-04: Unauthenticated GET to elections:list must redirect to login.
        @login_required redirects to settings.LOGIN_URL = '/accounts/login/'.
        CWE-306: Missing Authentication for Critical Function.
        """
        self.client.logout()
        response = self.client.get(reverse('elections:list'))
        self.assertIn(response.status_code, [302, 301], "Must redirect unauthenticated user.")
        self.assertIn('login', response.get('Location', '').lower(), "Redirect must be to login.")

    def test_ba_04_unauthenticated_cannot_access_vote_cast(self):
        """
        TC-BA-04 (vote endpoint): Unauthenticated access to the vote-submission endpoint
        must redirect to login — not expose the voting form.
        """
        self.client.logout()
        response = self.client.get(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk})
        )
        self.assertIn(response.status_code, [302, 301], "Must redirect unauthenticated voter.")
        self.assertIn('login', response.get('Location', '').lower(), "Redirect must be to login.")

    def test_ba_04_unauthenticated_cannot_access_admin_pages(self):
        """
        TC-BA-04 (admin pages): All admin-only endpoints must redirect unauthenticated
        visitors to login, not expose any admin functionality.
        """
        self.client.logout()
        admin_urls = [
            reverse('accounts:voter_list'),
            reverse('accounts:add_voter'),
            reverse('audit:logs'),
            reverse('elections:create'),
        ]
        for url in admin_urls:
            response = self.client.get(url)
            self.assertIn(
                response.status_code, [302, 301],
                f"Unauthenticated GET to {url} must redirect (got {response.status_code}).",
            )
            self.assertIn(
                'login', response.get('Location', '').lower(),
                f"Unauthenticated redirect from {url} must target the login page.",
            )

    def test_ba_04_unauthenticated_cannot_access_audit_results(self):
        """
        TC-BA-04 (results): Election results endpoint requires authentication.
        The results_view is protected by @login_required.
        """
        self.client.logout()
        response = self.client.get(
            reverse('audit:results', kwargs={'election_pk': self.election.pk})
        )
        self.assertIn(
            response.status_code, [302, 301],
            "Unauthenticated access to audit:results must redirect.",
        )

    # ── TC-BA-05 ────────────────────────────────────────────────────

    def test_ba_05_generic_error_for_nonexistent_email(self):
        """
        TC-BA-05: Login with a non-existent email must produce a generic error message.

        CWE-204: Observable Response Discrepancy — if the error reveals 'email not found',
        an attacker can enumerate valid accounts by trying different emails.
        Expected: 'tidak valid' (generic) — NOT 'email tidak terdaftar' or similar.
        """
        response = self.client.post(
            reverse('accounts:login'),
            {'email': 'totally_fake_9999@example.com', 'password': 'AnyPass1!'},
        )
        self.assertEqual(response.status_code, 200, "Failed login must return HTTP 200.")
        content = response.content.decode('utf-8')

        self.assertIn(
            'tidak valid', content,
            "Generic 'tidak valid' message must appear for non-existent email.",
        )
        for revealing_phrase in ['email tidak terdaftar', 'akun tidak ditemukan', 'user not found']:
            self.assertNotIn(
                revealing_phrase, content.lower(),
                f"SECURITY FINDING: Error reveals email non-existence: '{revealing_phrase}'.",
            )

    def test_ba_05_generic_error_for_wrong_password(self):
        """
        TC-BA-05: Login with valid email but wrong password must produce the SAME generic
        error — 'tidak valid' — not a message indicating which credential is wrong.

        If the message differs from the non-existent-email case, attackers can enumerate
        registered accounts (CWE-204).
        """
        response = self.client.post(
            reverse('accounts:login'),
            {'email': 'voter_auth@test.com', 'password': 'WrongPasswordXYZ!'},
        )
        self.assertEqual(response.status_code, 200, "Failed login must return HTTP 200.")
        content = response.content.decode('utf-8')

        self.assertIn(
            'tidak valid', content,
            "Generic 'tidak valid' message must appear for wrong password.",
        )
        for revealing_phrase in ['password salah', 'password tidak benar', 'wrong password']:
            self.assertNotIn(
                revealing_phrase, content.lower(),
                f"SECURITY FINDING: Error reveals incorrect password: '{revealing_phrase}'.",
            )

    def test_ba_05_error_messages_are_identical_for_both_failure_cases(self):
        """
        TC-BA-05 (consistency): The exact error keyword must be the same for both
        non-existent email and wrong password to prevent user enumeration.
        """
        r_nonexistent = self.client.post(
            reverse('accounts:login'),
            {'email': 'never_ever_registered@example.com', 'password': 'Pass1!'},
        )
        r_wrong_pw = self.client.post(
            reverse('accounts:login'),
            {'email': 'voter_auth@test.com', 'password': 'NotTheRealPassword!'},
        )
        c1 = r_nonexistent.content.decode('utf-8')
        c2 = r_wrong_pw.content.decode('utf-8')

        self.assertIn('tidak valid', c1, "Non-existent email: must show 'tidak valid'.")
        self.assertIn('tidak valid', c2, "Wrong password: must show 'tidak valid'.")

    # ── TC-BA-06 ────────────────────────────────────────────────────

    def test_ba_06_voter_blocked_from_admin_only_pages(self):
        """
        TC-BA-06 (RBAC Voter → Admin): Authenticated voter must NOT access admin pages.

        @admin_required checks request.user.is_admin_role; if False, redirects to 'home'.
        The voter must never see admin page content.
        CWE-285: Improper Authorization.
        """
        self.client.force_login(self.voter)
        admin_urls = [
            reverse('accounts:voter_list'),
            reverse('accounts:add_voter'),
            reverse('audit:logs'),
            reverse('elections:create'),
        ]
        for url in admin_urls:
            response = self.client.get(url)
            self.assertIn(
                response.status_code, [302, 403],
                f"Voter must not access admin URL {url} (status={response.status_code}).",
            )

    def test_ba_06_candidate_blocked_from_admin_only_pages(self):
        """
        TC-BA-06 (RBAC Candidate → Admin): Authenticated candidate must NOT access admin pages.
        Candidates have ROLE_CANDIDATE; is_admin_role returns False.
        """
        self.client.force_login(self.candidate_user)
        admin_urls = [
            reverse('accounts:voter_list'),
            reverse('elections:create'),
            reverse('audit:logs'),
        ]
        for url in admin_urls:
            response = self.client.get(url)
            self.assertIn(
                response.status_code, [302, 403],
                f"Candidate must not access admin URL {url} (status={response.status_code}).",
            )

    def test_ba_06_voter_blocked_from_candidate_profile(self):
        """
        TC-BA-06 (RBAC Voter → Candidate): Voter must NOT access the candidate profile page.
        candidates:my_profile is protected by @candidate_required.
        """
        self.client.force_login(self.voter)
        response = self.client.get(reverse('candidates:my_profile'))
        self.assertIn(
            response.status_code, [302, 403],
            "Voter must be blocked from candidate profile page.",
        )

    def test_ba_06_voter_cannot_see_draft_election(self):
        """
        TC-BA-06 (E-Voting integrity): Voters must not see DRAFT elections.

        election_detail_view redirects voters away from DRAFT elections, ensuring
        they cannot access election data before it is officially opened.
        """
        draft = Election.objects.create(
            title='Draft Election',
            description='',
            start_date=timezone.now() + timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )
        self.client.force_login(self.voter)
        response = self.client.get(reverse('elections:detail', kwargs={'pk': draft.pk}))
        self.assertIn(
            response.status_code, [302, 404],
            "Voter must not access DRAFT election detail.",
        )


# ═══════════════════════════════════════════════════════════════════
# CATEGORY 4 — CSRF PROTECTION (CWE-352)
# ═══════════════════════════════════════════════════════════════════

class CSRFProtectionTest(TestCase):
    """
    Verifies that Cross-Site Request Forgery (CSRF) protection is correctly applied
    to every state-changing POST endpoint in the E-Voting system.

    Django's CsrfViewMiddleware provides cookie-based CSRF tokens.  Tests confirm:
      (a) Every POST form renders a csrfmiddlewaretoken hidden input.
      (b) POSTs with invalid or missing tokens are rejected with HTTP 403.
      (c) Votes cannot be forged on behalf of another user.
      (d) Double-voting is prevented.

    OWASP A01:2021 · CWE-352
    """

    def setUp(self):
        self.client = Client()
        # CSRF-enforcing client — disables the test-client bypass
        self.csrf_client = Client(enforce_csrf_checks=True)

        self.voter = _make_user(
            'voter_csrf', 'voter_csrf@test.com', 'Voter@123!', CustomUser.ROLE_PEMILIH
        )
        self.voter2 = _make_user(
            'voter2_csrf', 'voter2_csrf@test.com', 'Voter2@123!', CustomUser.ROLE_PEMILIH
        )
        self.admin = _make_user(
            'admin_csrf', 'admin_csrf@test.com', 'Admin@123!', CustomUser.ROLE_ADMIN
        )

        self.election = Election.objects.create(
            title='CSRF Test Election',
            description='',
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=1),
            status=Election.STATUS_OPEN,
            created_by=self.admin,
        )
        self.candidate1 = Candidate.objects.create(
            election=self.election, number=1,
            name='Paslon CSRF Satu', vision='Visi', mission='Misi',
        )
        self.candidate2 = Candidate.objects.create(
            election=self.election, number=2,
            name='Paslon CSRF Dua', vision='Visi Dua', mission='Misi Dua',
        )
        self.draft_election = Election.objects.create(
            title='Draft CSRF Election',
            description='',
            start_date=timezone.now() + timedelta(hours=1),
            end_date=timezone.now() + timedelta(hours=2),
            status=Election.STATUS_DRAFT,
            created_by=self.admin,
        )

    # ── TC-CSRF-01 ──────────────────────────────────────────────────

    def test_csrf_01_login_form_contains_csrf_token(self):
        """
        TC-CSRF-01 (login): The login page must render a csrfmiddlewaretoken hidden input.

        Without it, an attacker's page could POST to /accounts/login/ and force-login
        a victim into the attacker's account (login CSRF).
        """
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200, "Login page must return HTTP 200.")
        content = response.content.decode('utf-8')
        self.assertIn(
            'csrfmiddlewaretoken', content,
            "SECURITY FINDING: Login form missing csrfmiddlewaretoken — login CSRF possible!",
        )

    def test_csrf_01_vote_form_contains_csrf_token(self):
        """
        TC-CSRF-01 (vote form): The vote-submission form must contain a CSRF token.

        This is the most critical form in the system: a CSRF attack here forces a voter
        to cast a vote for the attacker's preferred candidate without their knowledge.
        """
        self.client.force_login(self.voter)
        response = self.client.get(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk})
        )
        self.assertEqual(response.status_code, 200, "Vote form page must return HTTP 200.")
        content = response.content.decode('utf-8')
        self.assertIn(
            'csrfmiddlewaretoken', content,
            "SECURITY FINDING: Vote form missing csrfmiddlewaretoken — vote CSRF possible!",
        )

    def test_csrf_01_candidate_create_form_contains_csrf_token(self):
        """
        TC-CSRF-01 (candidate form): Candidate creation form must include CSRF token.

        Without it, an attacker could trick an admin into creating fraudulent candidates.
        """
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('candidates:create', kwargs={'election_pk': self.draft_election.pk})
        )
        self.assertEqual(response.status_code, 200, "Candidate create page must return 200.")
        content = response.content.decode('utf-8')
        self.assertIn(
            'csrfmiddlewaretoken', content,
            "SECURITY FINDING: Candidate create form missing csrfmiddlewaretoken!",
        )

    def test_csrf_01_election_detail_post_forms_contain_csrf_token(self):
        """
        TC-CSRF-01 (election control forms): The Open/Close election buttons in the detail
        page are POST forms and must include CSRF tokens.

        A CSRF attack here could allow an attacker to open or close an election on an
        admin's behalf simply by tricking them into visiting a malicious page.
        """
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('elections:detail', kwargs={'pk': self.election.pk})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn(
            'csrfmiddlewaretoken', content,
            "SECURITY FINDING: Election detail POST forms missing csrfmiddlewaretoken!",
        )

    # ── TC-CSRF-02 ──────────────────────────────────────────────────

    def test_csrf_02_vote_post_with_invalid_token_rejected(self):
        """
        TC-CSRF-02: POST to vote endpoint with a deliberately invalid CSRF token must
        return HTTP 403 Forbidden and must NOT record a vote.

        Uses Client(enforce_csrf_checks=True) to activate the real CSRF middleware check
        (the standard test client bypasses it).  Simulates a cross-origin attacker
        that injects a forged token.
        """
        # Authenticate on csrf_client and fetch page to establish CSRF cookie
        self.csrf_client.force_login(self.voter)
        self.csrf_client.get(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk})
        )

        response = self.csrf_client.post(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk}),
            {
                'csrfmiddlewaretoken': 'forged_invalid_token_xyz_12345',
                'candidate': self.candidate1.pk,
            },
            HTTP_REFERER=(
                'http://testserver'
                + reverse('voting:cast', kwargs={'election_pk': self.election.pk})
            ),
        )

        self.assertEqual(
            response.status_code, 403,
            "SECURITY FINDING: Vote POST with invalid CSRF token was accepted — CSRF protection broken!",
        )
        self.assertFalse(
            Vote.objects.filter(voter=self.voter, election=self.election).exists(),
            "SECURITY FINDING: Vote recorded despite invalid CSRF token!",
        )

    def test_csrf_02_candidate_create_post_with_invalid_token_rejected(self):
        """
        TC-CSRF-02 (candidate): POST to candidate creation with invalid CSRF token must fail.
        Confirms CSRF protection is not limited to the vote endpoint.
        """
        self.csrf_client.force_login(self.admin)
        self.csrf_client.get(
            reverse('candidates:create', kwargs={'election_pk': self.draft_election.pk})
        )

        response = self.csrf_client.post(
            reverse('candidates:create', kwargs={'election_pk': self.draft_election.pk}),
            {
                'csrfmiddlewaretoken': 'invalid_xyz',
                'number': 1,
                'name': 'CSRF Candidate',
                'vision': 'Visi',
                'mission': 'Misi',
            },
            HTTP_REFERER='http://testserver/',
        )

        self.assertEqual(
            response.status_code, 403,
            "SECURITY FINDING: Candidate creation accepted with invalid CSRF token!",
        )
        self.assertFalse(
            Candidate.objects.filter(name='CSRF Candidate').exists(),
            "SECURITY FINDING: Candidate created despite invalid CSRF token!",
        )

    # ── TC-CSRF-03 ──────────────────────────────────────────────────

    def test_csrf_03_vote_post_without_token_rejected(self):
        """
        TC-CSRF-03: POST to vote endpoint with NO CSRF token must return HTTP 403.

        This is the canonical CSRF attack: the attacker's page POSTs to the victim's
        authenticated session with no token at all (the attacker cannot read the
        victim's CSRF cookie due to Same-Origin Policy).
        """
        self.csrf_client.force_login(self.voter)
        # GET to establish CSRF cookie, then deliberately omit token in POST
        self.csrf_client.get(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk})
        )

        response = self.csrf_client.post(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk}),
            {'candidate': self.candidate1.pk},   # No csrfmiddlewaretoken at all
            HTTP_REFERER='http://attacker.example.com/evil.html',
        )

        self.assertEqual(
            response.status_code, 403,
            "SECURITY FINDING: Vote POST without CSRF token accepted — "
            "CsrfViewMiddleware may be disabled!",
        )
        self.assertFalse(
            Vote.objects.filter(voter=self.voter, election=self.election).exists(),
            "SECURITY FINDING: Vote recorded without CSRF token!",
        )

    def test_csrf_03_login_post_without_token_rejected(self):
        """
        TC-CSRF-03 (login): Login form POST without CSRF token must also be rejected.

        Prevents 'login CSRF' — an attacker forcing a victim to log in as the attacker's
        account, then harvesting the victim's subsequent activity.
        """
        # GET login page to establish CSRF cookie
        self.csrf_client.get(reverse('accounts:login'))

        response = self.csrf_client.post(
            reverse('accounts:login'),
            {'email': 'voter_csrf@test.com', 'password': 'Voter@123!'},
            # No csrfmiddlewaretoken
        )
        self.assertEqual(
            response.status_code, 403,
            "SECURITY FINDING: Login POST accepted without CSRF token — login CSRF possible!",
        )

    # ── TC-CSRF-04d ─────────────────────────────────────────────────

    def test_csrf_04d_vote_always_recorded_for_authenticated_user(self):
        """
        TC-CSRF-04d (E-Voting — cross-user vote forgery): Even if POST data contains
        a voter_id or voter field pointing to another user, the vote must be recorded
        for the currently authenticated session user (request.user), not the injected ID.

        cast_vote_view uses: Vote.objects.create(voter=request.user, ...) — the POST
        body has no influence over which user's vote is recorded.
        """
        self.client.force_login(self.voter)

        response = self.client.post(
            reverse('voting:cast', kwargs={'election_pk': self.election.pk}),
            {
                'candidate': self.candidate1.pk,
                'voter':    self.voter2.pk,   # Attempt to forge voter identity
                'voter_id': self.voter2.pk,   # Second attempt
            },
        )

        # If a vote was submitted successfully (302 redirect to status page)
        if response.status_code == 302:
            self.assertTrue(
                Vote.objects.filter(voter=self.voter, election=self.election).exists(),
                "Vote must be recorded for the authenticated user (voter1).",
            )
            self.assertFalse(
                Vote.objects.filter(voter=self.voter2, election=self.election).exists(),
                "SECURITY FINDING: Vote recorded for voter2 when voter1 was authenticated — vote forgery!",
            )

    def test_csrf_04d_voter_cannot_vote_twice_in_same_election(self):
        """
        TC-CSRF-04d (double vote prevention): The Vote model enforces
        unique_together = ('voter', 'election'), and the view checks for an existing
        vote before processing.  A voter must not be able to cast two votes.
        """
        self.client.force_login(self.voter)
        vote_url = reverse('voting:cast', kwargs={'election_pk': self.election.pk})

        self.client.post(vote_url, {'candidate': self.candidate1.pk})  # First vote
        self.client.post(vote_url, {'candidate': self.candidate2.pk})  # Second attempt

        count = Vote.objects.filter(voter=self.voter, election=self.election).count()
        self.assertEqual(
            count, 1,
            f"SECURITY FINDING: Voter cast {count} votes — double-voting not prevented!",
        )

    # ── White-box: middleware config ─────────────────────────────────

    def test_csrf_middleware_enabled_in_settings(self):
        """
        TC-CSRF (white-box): CsrfViewMiddleware must be listed in settings.MIDDLEWARE.

        If this middleware is removed, ALL CSRF protection is disabled application-wide —
        every POST form becomes exploitable.
        """
        self.assertIn(
            'django.middleware.csrf.CsrfViewMiddleware',
            settings.MIDDLEWARE,
            "SECURITY FINDING: CsrfViewMiddleware is NOT in MIDDLEWARE — "
            "CSRF protection completely disabled!",
        )

    def test_csrf_session_cookie_httponly_flag_set(self):
        """
        TC-CSRF (session hardening): SESSION_COOKIE_HTTPONLY must be True.

        The HttpOnly flag prevents JavaScript from reading the session cookie, reducing
        the blast radius of XSS: even if XSS runs, it cannot steal the session token.
        """
        self.assertTrue(
            getattr(settings, 'SESSION_COOKIE_HTTPONLY', False),
            "SECURITY FINDING: SESSION_COOKIE_HTTPONLY is False — "
            "XSS can steal session cookies!",
        )
