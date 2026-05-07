# E-Voting System — Pacil Voting

Sistem pemilihan umum berbasis web yang dibangun dengan Django dan SQLite. Dirancang untuk mendukung pemilihan organisasi secara digital dengan fokus pada keamanan, integritas data, dan kerahasiaan suara.

---

## Deskripsi Aplikasi

Aplikasi ini memungkinkan administrator mengelola pemilihan dan kandidat, sementara pemilih dapat memberikan suara secara online. Setiap suara dicatat dengan token anonim sehingga identitas pemilih tidak dapat dikaitkan dengan pilihan kandidat. Seluruh aktivitas penting dicatat dalam log audit yang dilindungi dengan hash SHA-256.

### Fitur Utama

- Autentikasi berbasis email dengan perlindungan brute-force (lockout setelah 5 kali gagal selama 15 menit)
- Manajemen pemilihan dengan alur status: **DRAFT → OPEN → CLOSED**
- Manajemen kandidat yang hanya dapat diubah saat pemilihan berstatus DRAFT
- Pencegahan double voting melalui transaksi atomik dan kunci database (`select_for_update`)
- Token suara anonim berbasis SHA-256 untuk menjaga kerahasiaan pilihan
- Log audit immutable dengan hash SHA-256 untuk deteksi tamper

---

## Struktur Modul (5 Django Apps)

| App          | Fungsi                                                    |
|--------------|-----------------------------------------------------------|
| `accounts`   | Autentikasi, manajemen pengguna, rate limiting login      |
| `elections`  | CRUD pemilihan, manajemen status (buka/tutup)             |
| `candidates` | CRUD kandidat per pemilihan                               |
| `voting`     | Pengambilan suara, pencegahan double voting               |
| `audit`      | Log audit sistem, tampilan hasil pemilihan                |

---

## Implementasi Keamanan

### 1. Pencegahan SQL Injection

**Kode rentan:**

```python
# Raw SQL dengan string interpolasi — rentan SQL Injection
cursor.execute(f"SELECT * FROM elections WHERE title = '{title}'")
```

**Kode aman (diimplementasikan):**

```python
# elections/views.py — seluruh query menggunakan Django ORM
Election.objects.filter(title=title)

# voting/views.py — transaksi atomik dengan select_for_update() untuk race condition
with transaction.atomic():
    if Vote.objects.select_for_update().filter(
        voter=request.user, election=election
    ).exists():
        return redirect('voting:status', election_pk=election_pk)
    Vote.objects.create(voter=request.user, election=election, candidate=candidate)
```

Django ORM secara otomatis menggunakan parameterized queries sehingga input pengguna tidak pernah diinterpolasi langsung ke SQL. Tidak ada penggunaan `cursor.execute()` dengan format string di seluruh codebase.

**CWE:** CWE-89 (SQL Injection)

---

### 2. Pencegahan Code Injection / XSS

**Kode rentan:**

```python
# Langsung menyimpan input pengguna tanpa sanitasi
candidate.name = request.POST.get('name')
```

**Kode aman (diimplementasikan):**

```python
# accounts/utils.py
import html, re

def sanitize_text(value):
    if not value:
        return value
    return html.escape(str(value).strip())

def is_safe_text(value, max_length=500):
    pattern = r'^[\w\s\.,\-\(\)\!\?\:\;\"\'\&\/\+\=\@\#\%\^\*\[\]àáâãäåæçèéêëìíîïðñòóôõöùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞ]+$'
    return bool(re.match(pattern, value, re.UNICODE)) and len(value) <= max_length
```

- `html.escape()` mengonversi karakter berbahaya (`<`, `>`, `"`, `'`) menjadi HTML entity sebelum disimpan
- Regex allowlist memvalidasi karakter yang diperbolehkan pada semua field teks bebas
- Template Django menggunakan auto-escaping secara default, menghasilkan double-escape yang aman
- Header Content-Security-Policy ditambahkan di `base.html` untuk membatasi sumber skrip

**CWE:** CWE-79 (Cross-site Scripting), CWE-94 (Code Injection / SSTI)

---

### 3. Broken Authentication — Rate Limiting & Session Security

**Kode rentan:**

```python
# Tidak ada pembatasan percobaan login
def login_view(request):
    user = authenticate(email=email, password=password)
    if user:
        login(request, user)
```

**Kode aman (diimplementasikan):**

```python
# accounts/models.py
class LoginAttempt(models.Model):
    @classmethod
    def is_locked_out(cls, email, max_attempts=5, minutes=15):
        window = timezone.now() - timedelta(minutes=minutes)
        failures = cls.objects.filter(
            email=email, success=False, timestamp__gte=window
        ).count()
        return failures >= max_attempts

# accounts/views.py
def login_view(request):
    if LoginAttempt.is_locked_out(email, max_attempts, lockout_minutes):
        AuditLog.log(action=AuditLog.ACTION_ACCOUNT_LOCKED, ...)
        messages.error(request, 'Akun terkunci sementara ...')
        return render(request, 'accounts/login.html', {'form': form})
    ...
    logout(request)
    request.session.flush()  # Invalidasi total session saat logout
```

Konfigurasi keamanan session di `settings.py`:

```python
SESSION_COOKIE_HTTPONLY = True        # Cegah akses JavaScript ke cookie
SESSION_COOKIE_SAMESITE = 'Lax'      # Proteksi CSRF via SameSite policy
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'             # Cegah clickjacking
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
```

Password disimpan menggunakan PBKDF2-SHA256 (default Django) — tidak pernah disimpan plaintext.

**CWE:** CWE-256 (Plaintext Storage of Password), CWE-307 (Brute Force), CWE-384 (Session Fixation), CWE-613 (Insufficient Session Expiration)

---

### 4. CSRF Protection

**Kode rentan:**

```html
<!-- Form tanpa CSRF token — rentan serangan cross-site -->
<form method="post" action="/voting/election/1/cast/">
  <button type="submit">Vote</button>
</form>
```

**Kode aman (diimplementasikan):**

```html
<!-- Semua form POST menyertakan CSRF token -->
<form method="post" action="{% url 'voting:cast' election.pk %}">
  {% csrf_token %}
  <button type="submit">Berikan Suara</button>
</form>
```

```python
# pacil_voting/settings.py
MIDDLEWARE = [
    'django.middleware.csrf.CsrfViewMiddleware',  # Aktif global
    ...
]
CSRF_COOKIE_HTTPONLY = True
```

Semua operasi write (login, logout, buat/edit pemilihan, tambah/hapus kandidat, berikan suara, hapus pengguna) menggunakan POST dengan `{% csrf_token %}`. Logout pun menggunakan POST — bukan link GET — untuk mencegah CSRF pada operasi logout.

**CWE:** CWE-352 (Cross-Site Request Forgery)

---

## Cara Instalasi & Menjalankan Proyek

### Prasyarat

- Python 3.10+
- pip

### Langkah Instalasi

```bash
# 1. Clone repositori
git clone <repo-url>
cd pkpl26_18_pkpletsgoo

# 2. Buat dan aktifkan virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# atau: venv\Scripts\activate   # Windows

# 3. Install dependensi
pip install -r pacil_voting/requirements.txt

# 4. Masuk ke direktori Django
cd pacil_voting

# 5. Jalankan migrasi database
python manage.py migrate

# 6. Buat akun admin
python manage.py createsuperuser
# Masukkan email, username, dan password saat diminta
# Kemudian buka /admin/ dan set role pengguna ke ADMIN

# 7. Jalankan server
python manage.py runserver
```

Akses aplikasi di **http://127.0.0.1:8000/**

---

## Alur Penggunaan

1. **Admin** login → buat pemilihan baru (status: DRAFT)
2. **Admin** tambah minimal 2 kandidat ke pemilihan
3. **Admin** tambah akun pemilih melalui menu manajemen voter
4. **Admin** buka pemilihan (status: OPEN)
5. **Pemilih** login → pilih pemilihan aktif → berikan suara
6. **Admin** tutup pemilihan (status: CLOSED)
7. **Semua pengguna** dapat melihat hasil setelah pemilihan ditutup

---

## Menjalankan Pengujian

```bash
# Dari dalam direktori pacil_voting/
python manage.py test
```

Seluruh 18 unit test mencakup model, autentikasi, rate limiting, double-vote prevention, dan audit logging.

---

## Teknologi

| Komponen   | Teknologi                             |
|------------|---------------------------------------|
| Backend    | Django 6.0.4                          |
| Database   | SQLite (built-in)                     |
| Frontend   | Bootstrap 5.3 (CDN), Bootstrap Icons  |
| Hashing    | SHA-256 (token anonim & log audit)    |
| Password   | PBKDF2-SHA256 (via Django auth)       |
| Static     | Whitenoise                            |

---

## Anggota Kelompok

| Nama | NPM | Modul |
|------|-----|-------|
|  |  | accounts |
|  |  | elections |
|  |  | candidates |
|  |  | voting |
|  |  | audit |
