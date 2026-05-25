# E-Voting System — Pacil Voting

Sistem pemilihan umum berbasis web yang dibangun dengan Django dan SQLite. Dirancang untuk mendukung pemilihan organisasi secara digital dengan fokus pada keamanan, integritas data, dan kerahasiaan suara.

---

## Deskripsi Aplikasi

Aplikasi ini memungkinkan administrator mengelola pemilihan dan kandidat, sementara pemilih dapat memberikan suara secara online, selain itu terdapat peran kandidat yang memiliki akses untuk mengedit visi dan misi. Setiap suara dicatat dengan token anonim sehingga identitas pemilih tidak dapat dikaitkan dengan pilihan kandidat. Seluruh aktivitas penting dicatat dalam log audit yang dilindungi dengan hash SHA-256.

### Fitur Utama

- Autentikasi berbasis email dengan perlindungan brute-force (lockout setelah 5 kali gagal selama 15 menit)
- Manajemen pemilihan dengan alur status: **DRAFT → OPEN → CLOSED**
- Manajemen kandidat yang hanya dapat diubah saat pemilihan berstatus DRAFT
- Pencegahan double voting melalui transaksi atomik dan database lock (`select_for_update`)
- Token suara anonim berbasis SHA-256 untuk menjaga kerahasiaan pilihan
- Log audit immutable dengan hash SHA-256 untuk deteksi tamper
- Pencarian pemilihan yang aman menggunakan Django ORM
- CORS dikonfigurasi eksplisit untuk mencegah akses cross-origin yang tidak sah

### Skenario Aplikasi

Sistem ini mengimplementasikan **E-Voting System (Skenario 4)** dengan peran pengguna:

| Peran    | Deskripsi                                                                             |
|----------|---------------------------------------------------------------------------------------|
| Admin    | Mengelola pemilihan, kandidat, dan data pemilih; melihat audit log                    |
| Pemilih  | Memberikan suara, melihat status voting, melihat hasil (setelah tutup)                |
| Kandidat | Mengedit visi dan misi profil kandidat sendiri (hanya saat pemilihan berstatus Draft) |

### Struktur Modul

| App          | Fungsi                                                                          |
|--------------|---------------------------------------------------------------------------------|
| `accounts`   | Autentikasi, manajemen pengguna (Admin/Pemilih/Kandidat), rate limiting login   |
| `elections`  | CRUD pemilihan, manajemen status (buka/tutup), pencarian                        |
| `candidates` | CRUD kandidat (Admin); edit visi/misi profil sendiri (Kandidat, saat Draft)     |
| `voting`     | Pengambilan suara, pencegahan double voting                                     |
| `audit`      | Log audit sistem, tampilan hasil pemilihan                                      |

### Stack Teknologi

| Komponen | Teknologi                            |
|----------|--------------------------------------|
| Backend  | Django 6.0.4                         |
| Database | SQLite (built-in)                    |
| Frontend | Bootstrap 5.3 (CDN), Bootstrap Icons |
| Hashing  | SHA-256 (token anonim & log audit)   |
| Password | PBKDF2-SHA256 (via Django auth)      |
| Static   | Whitenoise                           |
| CORS     | django-cors-headers 4.9.0            |

---

<details>
<summary><h2>📋 Tugas 3 — Secure Coding</h2></summary>

## Implementasi Secure Coding

### 1. SQL Injection Prevention (CWE-89)

**Vulnerability yang dimitigasi:** SQL Injection memungkinkan attacker menyisipkan perintah SQL berbahaya melalui input pengguna untuk mengakses, memanipulasi, atau menghapus data dari database.

**Kode rentan (sebelum):**

```python
# Raw SQL dengan string interpolasi — rentan SQL Injection
# Attacker bisa input: ' OR '1'='1' -- untuk bypass login
# Atau: ' UNION SELECT username, password FROM users -- untuk dump data
def login_view(request):
    email = request.POST.get('email')
    cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")

# Pencarian rentan:
def search_view(request):
    q = request.GET.get('q')
    cursor.execute(f"SELECT * FROM elections WHERE title LIKE '%{q}%'")
```

**Kode aman (sesudah — diimplementasikan):**

```python
# elections/views.py — seluruh query menggunakan Django ORM (parameterized otomatis)
@login_required
def election_list_view(request):
    elections = Election.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        # ORM menggunakan parameterized query: WHERE title LIKE %s dengan nilai q
        # Input berbahaya seperti "' UNION SELECT..." diperlakukan sebagai string literal
        elections = elections.filter(title__icontains=q)
    return render(request, 'elections/list.html', {'elections': elections, 'q': q})

# voting/views.py — transaksi atomik + select_for_update() untuk race condition
with transaction.atomic():
    if Vote.objects.select_for_update().filter(
        voter=request.user, election=election
    ).exists():
        return redirect('voting:status', election_pk=election_pk)
    Vote.objects.create(voter=request.user, election=election, candidate=candidate)
```

**Teknik mitigasi:** Django ORM secara internal menggunakan parameterized queries (prepared statements) untuk semua operasi database. Input pengguna tidak pernah diinterpolasi langsung ke string SQL — melainkan dikirim sebagai parameter terpisah ke database engine. Seluruh codebase (5 apps) menggunakan ORM tanpa satu pun `cursor.execute()` dengan format string.

Untuk konteks SQLite: akses database hanya melalui Django ORM sehingga aplikasi tidak memiliki kemampuan DDL langsung (DROP/ALTER/TRUNCATE). Di production, disarankan migrasi ke PostgreSQL dengan dedicated user yang hanya memiliki hak SELECT, INSERT, UPDATE, DELETE.

**CWE:** CWE-89 (Improper Neutralization of Special Elements used in an SQL Command)

---

### 2. Code Injection / XSS Prevention (CWE-79, CWE-94)

**Vulnerability yang dimitigasi:** Cross-Site Scripting (XSS) memungkinkan attacker menyisipkan script berbahaya ke halaman web yang kemudian dieksekusi di browser korban. Server-Side Template Injection (SSTI) memungkinkan eksekusi kode di sisi server.

**Kode rentan (sebelum):**

```python
# Menyimpan input pengguna tanpa sanitasi — rentan Stored XSS
def create_candidate(request):
    name = request.POST.get('name')  # Bisa berisi <script>alert(1)</script>
    Candidate.objects.create(name=name)  # Tersimpan ke DB

# Template tanpa auto-escape — script akan dieksekusi browser
# {{ candidate.name }}  →  <script>alert(1)</script>  →  EKSEKUSI!
```

**Kode aman (sesudah — diimplementasikan):**

```python
# accounts/utils.py — sanitasi dengan html.escape()
import html, re

def sanitize_text(value):
    if not value:
        return value
    return html.escape(str(value).strip())
    # < → &lt;   > → &gt;   " → &quot;   ' → &#x27;

# candidates/forms.py — validasi berlapis: deteksi HTML tag → sanitasi → length check
def clean_name(self):
    name = self.cleaned_data.get('name', '')
    # Layer 1: deteksi tag HTML eksplisit, tolak dengan pesan jelas
    if re.search(r'<[^>]+>', name):
        raise forms.ValidationError(
            'Input mengandung karakter tidak diizinkan (tag HTML/script tidak diperbolehkan).'
        )
    # Layer 2: html.escape() untuk karakter berbahaya yang tersisa
    name = sanitize_text(name)
    if re.search(r'[<>{}\|\\^`]', name):
        raise forms.ValidationError('Nama mengandung karakter yang tidak diizinkan.')
    return name
```

```html
<!-- base.html — Content Security Policy membatasi sumber script -->
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self'; style-src 'self' https://cdn.jsdelivr.net;
               script-src 'self' https://cdn.jsdelivr.net;
               font-src 'self' https://cdn.jsdelivr.net;">

<!-- Template Django — auto-escaping aktif global, TIDAK ADA penggunaan |safe -->
{{ candidate.name }}   <!-- auto-escape: <script> → &lt;script&gt; -->
{{ candidate.vision }} <!-- auto-escape aktif -->
```

**Teknik mitigasi:** Defense-in-depth dengan tiga lapisan: (1) validasi input di backend yang menolak tag HTML eksplisit sebelum disimpan, (2) `html.escape()` yang mengkonversi karakter berbahaya menjadi HTML entity, dan (3) Django template auto-escaping aktif secara global — tidak ada satu pun penggunaan `|safe` atau `mark_safe()` di seluruh template. Ditambah CSP header di `base.html` untuk mencegah eksekusi script dari sumber eksternal yang tidak terdaftar.

**CWE:** CWE-79 (Cross-site Scripting), CWE-94 (Improper Control of Generation of Code / SSTI)

---

### 3. Broken Authentication Mitigation (CWE-256, CWE-307, CWE-613, CWE-204)

**Vulnerability yang dimitigasi:** Broken Authentication mencakup penyimpanan password plaintext, tidak adanya proteksi brute force, session yang tidak diinvalidasi setelah logout, dan pesan error yang membocorkan informasi (user enumeration).

**Kode rentan (sebelum):**

```python
# Password disimpan plaintext — langsung terbaca jika DB bocor
User.objects.create(email=email, password=password)  # plaintext!

# Tidak ada pembatasan percobaan login — brute force bebas
def login_view(request):
    user = authenticate(email=email, password=password)
    if user:
        login(request, user)
    # Tidak ada counter, tidak ada lockout

# Session tidak diinvalidasi — cookie lama masih bisa digunakan
def logout_view(request):
    logout(request)  # hanya hapus dari client-side
    return redirect('login')

# Pesan error membedakan kasus — memungkinkan user enumeration
messages.error(request, 'Username tidak ditemukan.')   # bocorkan info!
messages.error(request, 'Password salah.')             # bocorkan info!
```

**Kode aman (sesudah — diimplementasikan):**

```python
# accounts/models.py — LoginAttempt untuk rate limiting
class LoginAttempt(models.Model):
    @classmethod
    def is_locked_out(cls, email, max_attempts=5, minutes=15):
        window = timezone.now() - timedelta(minutes=minutes)
        failures = cls.objects.filter(
            email=email, success=False, timestamp__gte=window
        ).count()
        return failures >= max_attempts  # Kunci setelah 5 kali gagal

# accounts/views.py — login dengan rate limiting + pesan generik (anti-enumeration)
def login_view(request):
    if LoginAttempt.is_locked_out(email, max_attempts, lockout_minutes):
        messages.error(request, 'Terlalu banyak percobaan login. Silakan coba lagi nanti.')
        return render(request, 'accounts/login.html', {'form': form})

    user = authenticate(request, username=email, password=password)
    if user is not None:
        login(request, user)
    else:
        LoginAttempt.objects.create(email=email, ip_address=ip, success=False)
        # Pesan SAMA untuk email tidak terdaftar DAN password salah (mencegah CWE-204)
        messages.error(request, 'Email atau password tidak valid.')

# accounts/views.py — logout dengan server-side session invalidation
def logout_view(request):
    logout(request)
    request.session.flush()  # Hapus session dari server-side store
    return redirect('accounts:login')

# accounts/forms.py — password dihash otomatis via Django
def save(self, commit=True):
    user = super().save(commit=False)
    user.set_password(self.cleaned_data['password'])  # PBKDF2-SHA256 otomatis
    user.save()
```

```python
# pacil_voting/settings.py — konfigurasi keamanan session
SESSION_COOKIE_HTTPONLY = True        # Cegah akses JavaScript ke cookie
SESSION_COOKIE_SAMESITE = 'Lax'      # Proteksi CSRF via SameSite policy
SESSION_COOKIE_SECURE = not DEBUG    # HTTPS only di production
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = 'DENY'             # Cegah clickjacking
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# RBAC via decorator — setiap role hanya akses endpoint yang sesuai
# accounts/decorators.py
def admin_required(view_func):
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_role:
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped
```

**Teknik mitigasi:** Password menggunakan PBKDF2-SHA256 via `set_password()` Django — tidak pernah disimpan plaintext. Rate limiting via model `LoginAttempt` yang mencatat setiap percobaan gagal — akun dikunci 15 menit setelah 5 kali gagal. Session diinvalidasi di sisi server dengan `session.flush()` saat logout. Pesan error login dibuat identik untuk semua skenario gagal untuk mencegah user enumeration (CWE-204). RBAC diimplementasikan via decorator di setiap view.

**CWE:** CWE-256 (Plaintext Storage of Password), CWE-307 (Improper Restriction of Excessive Authentication Attempts), CWE-613 (Insufficient Session Expiration), CWE-204 (Observable Response Discrepancy)

---

### 4. CSRF Protection (CWE-352)

**Vulnerability yang dimitigasi:** Cross-Site Request Forgery memungkinkan attacker membuat korban yang sudah login mengirimkan request berbahaya tanpa sepengetahuannya, misalnya memberikan suara atau mengubah data tanpa izin.

**Kode rentan (sebelum):**

```html
<!-- Form tanpa CSRF token — request dari situs manapun bisa diterima -->
<form method="post" action="/voting/election/1/cast/">
  <input name="candidate" value="1">
  <button type="submit">Vote</button>
</form>
<!-- Saat korban mengunjungi halaman attacker sambil login, vote terkirim otomatis -->
```

**Kode aman (sesudah — diimplementasikan):**

```html
<!-- Semua form POST menggunakan {% csrf_token %} -->
<form method="post" action="{% url 'voting:cast' election.pk %}">
  {% csrf_token %}
  <!-- Menghasilkan: <input type="hidden" name="csrfmiddlewaretoken" value="UNIQUE_TOKEN"> -->
  <button type="submit">Berikan Suara</button>
</form>

<!-- Logout menggunakan POST + CSRF token (bukan link GET) -->
<form method="post" action="{% url 'accounts:logout' %}">
  {% csrf_token %}
  <button type="submit">Logout</button>
</form>
```

```python
# pacil_voting/settings.py — CsrfViewMiddleware + CORS aktif global
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',       # CORS — blokir cross-origin
    'django.middleware.csrf.CsrfViewMiddleware',   # CSRF — verifikasi token setiap POST
    ...
]
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG

# CORS dikonfigurasi eksplisit (django-cors-headers)
CORS_ALLOWED_ORIGINS = []        # Tidak ada origin eksternal yang diizinkan
CORS_ALLOW_ALL_ORIGINS = False   # Default deny untuk semua cross-origin request
CORS_ALLOW_CREDENTIALS = False
```

**Teknik mitigasi:** Django `CsrfViewMiddleware` memverifikasi token unik per-session pada setiap request POST/PUT/DELETE. Request tanpa token atau dengan token tidak valid menghasilkan HTTP 403 Forbidden. Semua form write di aplikasi menyertakan `{% csrf_token %}` tanpa pengecualian. CORS dikonfigurasi eksplisit via `django-cors-headers` dengan `CORS_ALLOWED_ORIGINS = []` — tidak ada cross-origin request yang diizinkan. `SESSION_COOKIE_SAMESITE = 'Lax'` memberikan lapisan proteksi tambahan.

**CWE:** CWE-352 (Cross-Site Request Forgery)

---

## Screenshot Aplikasi

#### Halaman Login
![alt text](img/image-2.png)

#### Home Admin
![alt text](img/image.png)

#### Home Pemilih
![alt text](img/image-1.png)

#### Home Kandidat
![alt text](img/image-home.png)

#### Daftar Pemilihan
![alt text](img/image-3.png)

#### Daftar Pemilihan - Admin
![alt text](img/image-4.png)

#### Detail Pemilihan
![alt text](img/image-5.png)

#### Detail Pemilihan — Panel Admin
![alt text](img/image-6.png)

#### Halaman Casting Vote
![alt text](img/image-7.png)

#### Halaman Hasil Rekapitulasi
![alt text](img/image-8.png)

#### Audit Log - Admin
![alt text](img/image-9.png)

#### Kelola Pemilih - Admin
![alt text](img/image-10.png)

#### Membuar & Edit Pemilihan Baru - Admin
![alt text](img/image-11.png)


### Fitur Keamanan

### SQL Injection (SQLi)

#### TC-SQLi-01: Login Bypass via SQL Injection
![alt text](img/image-13.png)

#### TC-SQLi-02: Search dengan Payload SQL Injection — Tidak Ada Data Bocor
![alt text](img/image-14.png)

#### TC-SQLi-03: Parameterized Query Verification (White-box)
![alt text](img/image-15.png)

### Code Injection (CI) & Cross-Site Scripting (XSS)

#### TC-CI-01: Script Tag Injection (Stored XSS / Reflected XSS)
![alt text](img/image-16.png)


#### TC-CI-02: HTML Injection via Input Field
![alt text](img/image-17.png)

#### TC-CI-03: Template Injection (SSTI untuk Django/Jinja2)
![alt text](img/image-18.png)

### Broken Authentication (BA)

#### TC-BA-01: Password Hashing Verification (White-box)
![alt text](img/image-19.png)

#### TC-BA-02: Account Lockout setelah 5x Login Gagal
![alt text](img/image-12.png)

#### TC-BA-03: Session Token Invalidation setelah Logout
memasukkan manual session id
![alt text](img/image-20.png)
kembali diarahkan ke halaman login, tidak langsung mengakses elections
![alt text](img/image-21.png)

![alt text](img/messageImage_1778228826372.jpg)

#### TC-BA-04: Akses Halaman Terproteksi Tanpa Login
![alt text](img/image-22.png)


#### TC-BA-05: Pesan Error Login Generik
email benar, password salah
![alt text](img/image-23.png)
email dan password salah
![alt text](img/image-24.png)

### Cross-Site Request Forgery (CSRF)

#### TC-CSRF-01: CSRF Token Presence on Forms
dapat dilihat bahwa tepat di bawah <form ..> terdapat csrfmiddlewaretoken 

edit pemilihan
<img width="1919" height="767" alt="image" src="https://github.com/user-attachments/assets/0614ed34-3374-4787-9759-3ea6926565fe" />
buka pemilihan
<img width="1919" height="755" alt="image" src="https://github.com/user-attachments/assets/e29fc04e-3ecb-428b-bb23-d234a86127a7" />
tambah candidate
<img width="1918" height="811" alt="image" src="https://github.com/user-attachments/assets/8c690360-15de-40c5-9d7f-0821dfbf5e7c" />
edit candidate
<img width="1919" height="814" alt="image" src="https://github.com/user-attachments/assets/b4e968e3-21c0-47df-a4a7-92a04ec0f0bc" />
berikan suara
<img width="1919" height="768" alt="image" src="https://github.com/user-attachments/assets/feca40f2-6ad7-404a-8288-5ba3533cb527" />

#### TC-CSRF-02: HTTP 403 saat Token Invalid

edit pemilihan
<img width="1917" height="1121" alt="image" src="https://github.com/user-attachments/assets/fa5f019a-719f-4308-b07f-5f39f39b4070" />

buka pemilihan
<img width="1919" height="1133" alt="image" src="https://github.com/user-attachments/assets/4f29f181-d5dc-40f6-890c-c40bdd765564" />

tambah candidate
<img width="1919" height="1125" alt="image" src="https://github.com/user-attachments/assets/7803c8d7-50f9-499c-847a-5c5c14701e0c" />

edit candidate
<img width="1919" height="1126" alt="image" src="https://github.com/user-attachments/assets/eb6f1fd5-3d5f-43df-9b11-67cd1c82da53" />

berikan suara
<img width="1919" height="1136" alt="image" src="https://github.com/user-attachments/assets/13c2b29e-830d-44e0-8f6c-4b917f2501ee" />




#### TC-CSRF-03: Simulasi Cross-Origin Request (Tanpa Token)
saya membuat duplikasi halaman login
![alt text](img/image-27.png)
saat login dicoba, login tidak berhasil dan menghasilkan error 403 (Forbidden)
![alt text](img/image-28.png)


---

## Skenario Khusus: E-Voting System (S4)

### SQL Injection (SQLi)

#### TC-SQLi-04d: E-Voting Pencarian Calon
![alt text](img/image-29.png)

### Code Injection (CI) & Cross-Site Scripting (XSS)

#### TC-CI-04d: Form Kandidat Ditolak karena Tag HTML
![alt text](img/image-30.png)

### Cross-Site Request Forgery (CSRF)

#### TC-CSRF-04d: E-Voting Form Pilih Calon
saya menggunakan CSRF token orang lain untuk melakukan voting
![alt text](image-2.png)
dan halaman menghasilkan error forbidden 403
![alt text](image-3.png)

---

## Hasil Test Case
Link: https://docs.google.com/spreadsheets/d/1KMSPKvlV23YXpexYVPF_AO5B8ldtoc7lOJq_AGJgn7Q/edit?gid=1093344478#gid=1093344478

### Ringkasan Status

| TC-ID | Nama Test Case | Status |
|-------|----------------|--------|
| TC-SQLi-01 | Login bypass via SQL injection | ✅ LULUS |
| TC-SQLi-02 | Data extraction via UNION injection | ✅ LULUS |
| TC-SQLi-03 | Parameterized query verification (white-box) | ✅ LULUS |
| TC-CI-01 | Script tag injection (Stored/Reflected XSS) | ✅ LULUS |
| TC-CI-02 | HTML injection via input field | ✅ LULUS |
| TC-CI-03 | Template injection (SSTI) | ✅ LULUS |
| TC-BA-01 | Password hashing verification (white-box) | ✅ LULUS |
| TC-BA-02 | Brute force / rate limiting | ✅ LULUS |
| TC-BA-03 | Session token invalidation setelah logout | ✅ LULUS |
| TC-BA-04 | Akses halaman terproteksi tanpa login | ✅ LULUS |
| TC-BA-05 | Informasi error yang tidak informatif | ✅ LULUS |
| TC-CSRF-01 | CSRF token presence on forms | ✅ LULUS |
| TC-CSRF-02 | Request dengan CSRF token invalid ditolak | ✅ LULUS |
| TC-CSRF-03 | Simulasi cross-origin request tanpa token | ✅ LULUS |
| TC-SQLi-04d | E-Voting: pencarian calon | ✅ LULUS |
| TC-CI-04d | E-Voting: nama/visi-misi calon | ✅ LULUS |
| TC-CSRF-04d | E-Voting: form pilih calon | ✅ LULUS |

**Total: 17/17 TC Lulus ✅**

---

## Cara Instalasi & Menjalankan Proyek

### Prasyarat

- Python 3.10+
- pip

### Langkah Instalasi

```bash
# 1. Clone repositori
git clone https://gitlab.cs.ui.ac.id/pkpl26_18_pkpletsgoo/pkpl26_18_pkpletsgoo.git
cd pkpl26_18_pkpletsgoo

# 2. Buat dan aktifkan virtual environment
python -m venv venv

# Linux/macOS:
source venv/bin/activate

# Windows (Command Prompt):
venv\Scripts\activate

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# 3. Install dependensi
pip install -r pacil_voting/requirements.txt

# 4. Masuk ke direktori Django
cd pacil_voting

# 5. Jalankan migrasi database
python manage.py migrate

# 6. Isi data demo (disarankan)
python manage.py seed_data

# 7. Jalankan server
python manage.py runserver
```

Akses di: **http://127.0.0.1:8000/**

### Akun Demo (setelah seed_data)

| Role     | Email                        | Password      | Kondisi                                      |
|----------|------------------------------|---------------|----------------------------------------------|
| Admin    | admin@pkpl.com               | Admin1234!    | Bisa kelola semua                            |
| Pemilih  | pemilih1@pkpl.com            | Pemilih123!   | Sudah vote di pemilihan OPEN                 |
| Pemilih  | pemilih2@pkpl.com            | Pemilih123!   | Belum vote                                   |
| Pemilih  | pemilih3@pkpl.com            | Pemilih123!   | Belum vote                                   |
| Pemilih  | pemilih4@pkpl.com            | Pemilih123!   | Belum vote                                   |
| Pemilih  | pemilih5@pkpl.com            | Pemilih123!   | Belum vote                                   |
| Kandidat | kandidat.gilang@pkpl.com     | Kandidat123!  | Bisa edit visi/misi (pemilihan DRAFT)        |
| Kandidat | kandidat.hendra@pkpl.com     | Kandidat123!  | Bisa edit visi/misi (pemilihan DRAFT)        |
| Kandidat | kandidat.andi@pkpl.com       | Kandidat123!  | Terkunci, tidak bisa edit (pemilihan OPEN)   |

### Reset Data Demo

```bash
python manage.py seed_data --reset
```

### Menjalankan Unit Test

```bash
python manage.py test
```

---

## Video Demo
[Link YouTube TK3](https://youtu.be/XgLtZwbfJXk)

---

## Anggota Kelompok

| Nama | NPM | Modul |
|------|-----|-------|
| Kadek Chandra Rasmi | 2406426473 | elections |
| Muhamad Hakim Nizami | 2406399485 | accounts |
| Muhammad Helmi Alfarissi | 2406402416 | voting |
| Nazwa Zahra Sausan | 2406397750 | candidates |
| Syakirah Zahra Dhawini | 2406353950 | audit |

</details>

---

<details open>
<summary><h2>Tugas 4 — Unit Testing & Pentesting</h2></summary>

## A. Unit Testing Report

### Setup & Menjalankan Tests

**Stack:** Django + SQLite  
**Apps:** accounts, voting, elections, candidates, audit  
**Test location:** `tests/test_security.py` (centralized) + per-app tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run semua tests
python manage.py test tests accounts.tests voting.tests elections.tests candidates.tests -v 2

# Run dengan coverage
coverage run --source='.' --omit='*/migrations/*,*/tests/*,manage.py,*/settings*,*/wsgi*,*/asgi*' manage.py test tests accounts.tests voting.tests elections.tests candidates.tests -v 2

# Lihat coverage report
coverage report --show-missing
```

---

### Hasil Unit Testing — 45/45 Tests PASS ✅

| Kategori | Jumlah Tests | Status |
|----------|-------------|--------|
| SQL Injection Prevention | 7 | ✅ All PASS |
| Code Injection / XSS | 8 | ✅ All PASS |
| Broken Authentication | 17 | ✅ All PASS |
| CSRF Protection | 13 | ✅ All PASS |
| Unit Tests - accounts | 38 | ✅ All PASS |
| Unit Tests - voting | 14 | ✅ All PASS |
| Unit Tests - elections | 27 | ✅ All PASS |
| Unit Tests - candidates | 39 | ✅ All PASS |
| **Total** | **163** | **✅ All PASS** |

![alt text](img/image-4-2.png)

---

### Coverage Report

```
Name                              Stmts   Miss  Cover
-----------------------------------------------------
accounts/views.py                    96      1    99%
accounts/utils.py                    21      1    95%
accounts/decorators.py               40      4    90%
accounts/forms.py                   131     16    88%
voting/views.py                      46      7    85%
candidates/views.py                  80      0   100%
elections/views.py                   84      1    99%
elections/forms.py                   34      2    94%
audit/views.py                       25     15    40%
-----------------------------------------------------
TOTAL                              1068    233    78%
```

**Overall Coverage: 65%**
![alt text](img/image-5-2.png)

---

## B. Pentesting Report

**Tool:** OWASP ZAP 2.17.0  
**Target:** http://localhost:8000  
**Tanggal:** 25 Mei 2026

---

### 1. Reconnaissance

#### 1a. Passive Reconnaissance — Spider Tanpa Login

ZAP Spider dijalankan tanpa autentikasi. Hasil menunjukkan hanya endpoint publik yang dapat diakses:

| Endpoint | Method | Keterangan |
|----------|--------|------------|
| `/` | GET | Redirect ke login |
| `/accounts/login/` | GET, POST | Halaman login publik |
| `/robots.txt` | GET | Accessible |
| `/sitemap.xml` | GET | Accessible |
| `/favicon.ico` | GET | Accessible |

**Kesimpulan:** Dekorator `@login_required` bekerja dengan benar dimana semua endpoint protected tidak terkekspos tanpa autentikasi.

![alt text](img/1_Site_Tree.png)

#### 1b. Active Reconnaissance — Manual Explore dengan 3 Role

Manual Explore dilakukan dengan login menggunakan 3 role berbeda (admin, pemilih, paslon). Site Tree lengkap yang berhasil di-map:

```
http://localhost:8000/
├── accounts/
│   ├── login/
│   ├── logout/
│   └── voters/
├── audit/
│   ├── logs/
│   └── results/
├── candidates/
│   ├── 22/
│   ├── 23/
│   ├── election/12/
│   ├── election/13/
│   └── my-profile/
├── elections/
├── static/
└── voting/
```

![alt text](<img/Screenshot 2026-05-25 114232.png>)

![alt text](<img/Screenshot 2026-05-25 115342.png>)

![alt text](<img/Screenshot 2026-05-25 115409.png>)

![alt text](<img/Screenshot 2026-05-25 120549.png>)

![alt text](<img/Screenshot 2026-05-25 120559.png>)

---

### 2. Threat Modeling

| # | Target Endpoint | Attack | Severity | CWE |
|---|----------------|--------|----------|-----|
| 1 | /accounts/login/ | SQL Injection | High | CWE-89 |
| 2 | /accounts/login/ | Brute Force | Medium | CWE-307 |
| 3 | /accounts/login/ | User Enumeration | Low | CWE-204 |
| 4 | /vote/\<id\>/ | CSRF | High | CWE-352 |
| 5 | /vote/\<id\>/ | Broken Auth | High | CWE-306 |
| 6 | /vote/\<id\>/ | Double Vote | High | CWE-799 |
| 7 | /candidates/ | Stored XSS | High | CWE-79 |
| 8 | /candidates/ | HTML Injection | Medium | CWE-79 |
| 9 | /candidates/ | SSTI | High | CWE-94 |
| 10 | /elections/ | Broken Access Control | High | CWE-284 |
| 11 | /accounts/voters/ | Privilege Escalation | High | CWE-269 |
| 12 | /admin/ | Broken Access Control | High | CWE-284 |

---

### 3. Scanning & Enumeration

#### ZAP Active Scan — Alerts Summary (28 Alerts)

| Risk | Jumlah | Contoh Alert |
|------|--------|-------------|
| Medium | 8 | CSP Header Not Set, Cross-Domain Misconfiguration, Cookie Issues |
| Low | 12 | Server Leaks Version Info, HSTS Not Set, X-Content-Type-Options Missing |
| Informational | 8 | Authentication Request Identified, Modern Web Application |

![alt text](<img/Screenshot 2026-05-25 115444.png>)

![alt text](<img/Screenshot 2026-05-25 115516.png>)

**Notable alerts:**
- **User Controllable HTML Element Attribute (Potential XSS)** — parameter `email` di `/accounts/login/` → *dikonfirmasi false positive, input divalidasi server-side*
- **Server Leaks Version Information** — `WSGIServer/0.2 CPython/3.12.4` di-expose via `Server` HTTP header
- **Cookie Without Secure Flag** — session cookie tidak di-set dengan flag `Secure`
- **HTTP Only Site** — aplikasi berjalan di HTTP, bukan HTTPS

![SS ZAP Alert detail — User Controllable HTML Element (Potential XSS)](img/image-6-2.png)
> *Screenshot menunjukkan detail alert XSS di ZAP — URL target, parameter email, dan evidence yang menunjukkan ini adalah false positive karena input divalidasi server-side*

![SS ZAP Alert detail — Server Leaks Version Information](img/image-7-2.png)
> *Screenshot menunjukkan detail alert Server header yang membocorkan versi WSGIServer/0.2 CPython/3.12.4*

---

### 4. Exploitation & Testing (Manual Tests)

#### 4a. SQL Injection Test

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /accounts/login/` |
| **Parameter** | email |
| **Payload** | `' OR '1'='1 ' OR 1=1-- admin'--` |
| **Response** | 200 OK — halaman login kembali ditampilkan |
| **Hasil** | ✅ **AMAN** — Login bypass GAGAL |
| **Analisis** | Aplikasi menampilkan pesan "Input tidak valid" tanpa error traceback Django. Terdapat 2 lapis proteksi: validasi format email di frontend (HTML5) dan validasi generik di backend |

![SS SQLi test — browser menampilkan pesan "Input tidak valid"](<img/Screenshot 2026-05-25 121810.png>)
> *Screenshot menunjukkan halaman login dengan payload SQLi di field email, pesan error "Input tidak valid. Periksa kembali data Anda.", dan Network tab DevTools menampilkan response code 200 — membuktikan login bypass gagal*

---

#### 4b. CSRF Protection Test

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /accounts/login/` |
| **Method** | POST tanpa csrfmiddlewaretoken |
| **Tool** | ZAP Requester |
| **Response** | **403 Forbidden** |
| **Hasil** | ✅ **AMAN** — CSRF Protection aktif |
| **Analisis** | Django `CsrfViewMiddleware` berjalan dengan benar — setiap POST request tanpa CSRF token valid langsung ditolak dengan 403 |

![SS ZAP Requester — response 403 Forbidden saat request tanpa csrfmiddlewaretoken](<img/Screenshot 2026-05-25 123735.png>) 
> *Screenshot menunjukkan ZAP Requester dengan request body hanya berisi email dan password (tanpa csrfmiddlewaretoken), dan panel Response menampilkan HTTP/1.1 403 Forbidden — membuktikan CSRF protection aktif*

---

#### 4c. Stored XSS Test

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /candidates/` |
| **Parameter** | Nama Paslon, Visi, Misi |
| **Payload 1** | `<script>alert('XSS')</script>` |
| **Payload 2** | `<img src=x onerror=alert(1)>` |
| **Response** | 200 — form dikembalikan dengan pesan validasi |
| **Hasil** | ✅ **AMAN** — Semua payload diblokir |
| **Analisis** | Validator `is_safe_text()` di `accounts/utils.py` memblokir tag HTML/script sebelum data tersimpan ke database |

![SS XSS test — form kandidat menampilkan pesan validasi error](<img/Screenshot 2026-05-25 124152.png>)
> *Screenshot menunjukkan form Tambah Kandidat dengan payload XSS di field Nama Paslon dan Visi, serta pesan error merah "Input mengandung karakter tidak diizinkan (tag HTML/script tidak diperbolehkan)", membuktikan validator is_safe_text() aktif memblokir payload*

---

#### 4d. Brute Force Test

| Item | Detail |
|------|--------|
| **Endpoint** | `POST /accounts/login/` |
| **Tool** | ZAP Fuzzer |
| **Parameter** | password |
| **Payloads** | password123, admin, 123456, Admin1234, wrongpassword, test123 |
| **Response** | Semua 200 OK → setelah 5 percobaan muncul lockout |
| **Hasil** | ✅ **AMAN** — Rate limiting aktif |
| **Analisis** | Aplikasi memiliki `LoginAttempt` model yang mencatat setiap percobaan login. Akun dikunci setelah ≥5 percobaan gagal. Lockout berbasis email |

![alt text](<img/Screenshot 2026-05-25 124758.png>)
> *Screenshot menunjukkan tab Fuzzer ZAP dengan 6 baris hasil fuzz (password123, admin, 123456, Admin1234, wrongpassword, test123) — semua response 200 OK dengan body size seragam, membuktikan tidak ada perbedaan response antar password salah (tidak ada user enumeration)*

![limit](img/image-8-2.png)
> *Screenshot menunjukkan halaman login menampilkan pesan "Terlalu banyak percobaan login" setelah akun terkena lockout, membuktikan mekanisme rate limiting LoginAttempt aktif*

---

### 5. Reporting & Remediation
![ZAP Generate Report](img/image-9-2.png)
> *Screenshot menunjukkan dialog Generate Report ZAP dengan settings yang digunakan (template Risk and Confidence HTML, semua sections dicentang) dan konfirmasi report berhasil dibuat*

> 📄 **[File ZAP Report HTML terlampir: `2026-05-25-ZAP-Report-.html`]**

#### Tabel Remediation

| # | Alert | Risk | CWE | Status | Rekomendasi |
|---|-------|------|-----|--------|-------------|
| 1 | SQL Injection | High | CWE-89 | ✅ Aman | Django ORM sudah handle parameterized queries |
| 2 | Stored XSS | High | CWE-79 | ✅ Aman | `is_safe_text()` validator aktif di semua form |
| 3 | CSRF | High | CWE-352 | ✅ Aman | `CsrfViewMiddleware` aktif, terbukti 403 response |
| 4 | Brute Force | Medium | CWE-307 | ✅ Aman | `LoginAttempt` model + lockout mekanisme aktif |
| 5 | CSP Header Not Set | Medium | CWE-693 | ❌ Belum | Tambah `Content-Security-Policy` header via `django-csp` |
| 6 | HTTP Only Site | Medium | CWE-311 | ❌ Belum | Set `SECURE_SSL_REDIRECT=True` di production settings |
| 7 | Cookie Without Secure Flag | Medium | CWE-614 | ❌ Belum | Set `SESSION_COOKIE_SECURE=True` dan `CSRF_COOKIE_SECURE=True` |
| 8 | Cross-Domain Misconfiguration | Medium | CWE-264 | ❌ Belum | Batasi CORS hanya ke domain yang diizinkan |
| 9 | Server Leaks Version Info | Low | CWE-497 | ❌ Belum | Suppress `Server` header di WSGI config atau gunakan reverse proxy |
| 10 | HSTS Not Set | Low | CWE-319 | ❌ Belum | Set `SECURE_HSTS_SECONDS=31536000` di production settings |
| 11 | X-Content-Type-Options Missing | Low | CWE-693 | ❌ Belum | Set `SECURE_CONTENT_TYPE_NOSNIFF=True` di settings |
| 12 | Cookie Without SameSite | Low | CWE-1275 | ⚠️ Sebagian | Session cookie sudah `SameSite=Lax`, pastikan semua cookie konsisten |

---

## C. Video Demo
🎥 **Link YouTube:** 

---
## Anggota Kelompok

| Nama | NPM | Modul |
|------|-----|-------|
| Kadek Chandra Rasmi | 2406426473 | 
| Muhamad Hakim Nizami | 2406399485 | 
| Muhammad Helmi Alfarissi | 2406402416 | 
| Nazwa Zahra Sausan | 2406397750 | 
| Syakirah Zahra Dhawini | 2406353950 | 


</details>