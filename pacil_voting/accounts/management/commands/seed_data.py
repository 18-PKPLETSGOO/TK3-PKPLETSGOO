"""
Management command untuk mengisi database dengan data awal demo.

Jalankan dengan:
    python manage.py seed_data           # tambah data (skip jika sudah ada)
    python manage.py seed_data --reset   # hapus semua data lalu isi ulang
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from accounts.models import CustomUser
from elections.models import Election
from candidates.models import Candidate
from voting.models import Vote
from audit.models import AuditLog


ADMIN_EMAIL = 'admin@pkpl.com'
ADMIN_PASSWORD = 'Admin1234!'
ADMIN_USERNAME = 'admin'

VOTERS = [
    {'email': 'pemilih1@pkpl.com', 'password': 'Pemilih123!', 'username': 'pemilih1',
     'first_name': 'Budi', 'last_name': 'Santoso', 'nim': '2406000001'},
    {'email': 'pemilih2@pkpl.com', 'password': 'Pemilih123!', 'username': 'pemilih2',
     'first_name': 'Siti', 'last_name': 'Rahayu', 'nim': '2406000002'},
    {'email': 'pemilih3@pkpl.com', 'password': 'Pemilih123!', 'username': 'pemilih3',
     'first_name': 'Ahmad', 'last_name': 'Fauzi', 'nim': '2406000003'},
    {'email': 'pemilih4@pkpl.com', 'password': 'Pemilih123!', 'username': 'pemilih4',
     'first_name': 'Dewi', 'last_name': 'Anggraini', 'nim': '2406000004'},
    {'email': 'pemilih5@pkpl.com', 'password': 'Pemilih123!', 'username': 'pemilih5',
     'first_name': 'Rizky', 'last_name': 'Pratama', 'nim': '2406000005'},
]

# Kandidat user: (election_key, candidate_number, email, password, username, first_name, last_name)
# election_key: 'draft' = bisa edit visi/misi | 'open' = terkunci
CANDIDATE_USERS = [
    {
        'email': 'kandidat.gilang@pkpl.com', 'password': 'Kandidat123!',
        'username': 'kandidat_gilang', 'first_name': 'Gilang', 'last_name': 'Ramadhan',
        'election_key': 'draft', 'candidate_number': 1,
    },
    {
        'email': 'kandidat.hendra@pkpl.com', 'password': 'Kandidat123!',
        'username': 'kandidat_hendra', 'first_name': 'Hendra', 'last_name': 'Wijaya',
        'election_key': 'draft', 'candidate_number': 2,
    },
    {
        'email': 'kandidat.andi@pkpl.com', 'password': 'Kandidat123!',
        'username': 'kandidat_andi', 'first_name': 'Andi', 'last_name': 'Kurniawan',
        'election_key': 'open', 'candidate_number': 1,
    },
]


class Command(BaseCommand):
    help = 'Mengisi database dengan data demo untuk pengujian'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Hapus semua data lama sebelum membuat data baru',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Menghapus data lama...')
            Vote.objects.all().delete()
            AuditLog.objects.all().delete()
            Candidate.objects.all().delete()
            Election.objects.all().delete()
            CustomUser.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.WARNING('Data lama dihapus.'))

        now = timezone.now()

        # ── 1. Buat Admin ───────────────────────────────────────────────────
        admin, created = CustomUser.objects.get_or_create(
            email=ADMIN_EMAIL,
            defaults={
                'username': ADMIN_USERNAME,
                'first_name': 'Admin',
                'last_name': 'PKPL',
                'role': CustomUser.ROLE_ADMIN,
                'is_staff': True,
            }
        )
        if created:
            admin.set_password(ADMIN_PASSWORD)
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'Admin dibuat: {ADMIN_EMAIL}'))
        else:
            self.stdout.write(f'Admin sudah ada: {ADMIN_EMAIL}')

        # ── 2. Buat Pemilih ─────────────────────────────────────────────────
        voter_objects = []
        for v in VOTERS:
            voter, created = CustomUser.objects.get_or_create(
                email=v['email'],
                defaults={
                    'username': v['username'],
                    'first_name': v['first_name'],
                    'last_name': v['last_name'],
                    'nim': v['nim'],
                    'role': CustomUser.ROLE_PEMILIH,
                }
            )
            if created:
                voter.set_password(v['password'])
                voter.save()
                self.stdout.write(self.style.SUCCESS(f'Pemilih dibuat: {v["email"]}'))
            else:
                self.stdout.write(f'Pemilih sudah ada: {v["email"]}')
            voter_objects.append(voter)

        # ── 3. Pemilihan 1: OPEN (aktif sekarang, bisa divote) ──────────────
        election_open, _ = Election.objects.get_or_create(
            title='Pemilihan Ketua BEM Fasilkom 2026',
            defaults={
                'description': (
                    'Pemilihan Ketua Badan Eksekutif Mahasiswa Fakultas Ilmu Komputer '
                    'Universitas Indonesia periode 2026-2027. Pemilihan dilakukan secara '
                    'elektronik untuk memastikan transparansi dan akuntabilitas.'
                ),
                'start_date': now - timedelta(hours=2),
                'end_date': now + timedelta(hours=22),
                'status': Election.STATUS_OPEN,
                'created_by': admin,
            }
        )

        Candidate.objects.get_or_create(
            election=election_open, number=1,
            defaults={
                'name': 'Paslon MAJU — Andi Kurniawan & Lestari Dewi',
                'vision': 'Mewujudkan BEM Fasilkom yang inklusif, inovatif, dan berdampak nyata bagi seluruh mahasiswa.',
                'mission': (
                    '1. Membuka program mentoring lintas angkatan\n'
                    '2. Membangun portal informasi akademik terpadu\n'
                    '3. Mengadakan kompetisi programming tingkat nasional\n'
                    '4. Menjalin kemitraan dengan industri teknologi terkemuka'
                ),
            }
        )
        Candidate.objects.get_or_create(
            election=election_open, number=2,
            defaults={
                'name': 'Paslon BERSAMA — Reza Firmansyah & Nadia Putri',
                'vision': 'Bersama membangun ekosistem mahasiswa yang kolaboratif dan berprestasi.',
                'mission': (
                    '1. Mendirikan co-working space khusus mahasiswa Fasilkom\n'
                    '2. Program beasiswa bagi mahasiswa berprestasi kurang mampu\n'
                    '3. Festival teknologi tahunan dengan peserta dari seluruh Indonesia\n'
                    '4. Sistem aspirasi mahasiswa yang transparan dan responsif'
                ),
            }
        )
        Candidate.objects.get_or_create(
            election=election_open, number=3,
            defaults={
                'name': 'Paslon DIGITAL — Farhan Hidayat & Melisa Sanjaya',
                'vision': 'Digitalisasi layanan mahasiswa menuju kampus masa depan.',
                'mission': (
                    '1. Aplikasi mobile untuk layanan administrasi mahasiswa\n'
                    '2. Workshop keterampilan digital gratis setiap semester\n'
                    '3. Database alumni untuk jaringan karier mahasiswa\n'
                    '4. Kolaborasi riset dengan laboratorium Fasilkom'
                ),
            }
        )

        # pemilih1 sudah vote di pemilihan OPEN (untuk demo double-vote prevention)
        candidate_open_1 = Candidate.objects.get(election=election_open, number=1)
        Vote.objects.get_or_create(
            voter=voter_objects[0],
            election=election_open,
            defaults={'candidate': candidate_open_1}
        )
        self.stdout.write(self.style.SUCCESS(
            f'Pemilihan OPEN dibuat: "{election_open.title}" '
            f'(pemilih1 sudah vote)'
        ))

        # ── 4. Pemilihan 2: CLOSED (ada hasil rekapitulasi) ─────────────────
        election_closed, _ = Election.objects.get_or_create(
            title='Pemilihan Ketua Himpunan Mahasiswa Ilmu Komputer 2025',
            defaults={
                'description': (
                    'Pemilihan Ketua Himpunan Mahasiswa Ilmu Komputer periode 2025-2026. '
                    'Pemilihan telah selesai dilaksanakan.'
                ),
                'start_date': now - timedelta(days=30),
                'end_date': now - timedelta(days=29),
                'status': Election.STATUS_CLOSED,
                'created_by': admin,
            }
        )

        cand_c1, _ = Candidate.objects.get_or_create(
            election=election_closed, number=1,
            defaults={
                'name': 'Paslon SOLID — Kevin Prasetyo & Yasmine Nur',
                'vision': 'Himpunan yang solid, aktif, dan relevan di era digital.',
                'mission': (
                    '1. Reaktivasi komunitas riset mahasiswa\n'
                    '2. Program magang bersama perusahaan teknologi\n'
                    '3. Pelatihan soft skills dan leadership\n'
                    '4. Penerbitan jurnal ilmiah mahasiswa'
                ),
            }
        )
        cand_c2, _ = Candidate.objects.get_or_create(
            election=election_closed, number=2,
            defaults={
                'name': 'Paslon KREATIF — Dian Permata & Bagas Wicaksono',
                'vision': 'Kreativitas dan inovasi sebagai fondasi himpunan yang maju.',
                'mission': (
                    '1. Hackathon internal semester ganjil dan genap\n'
                    '2. Gallery showcase proyek mahasiswa\n'
                    '3. Podcast teknologi bulanan\n'
                    '4. Kolaborasi dengan UKM seni untuk kegiatan lintas minat'
                ),
            }
        )

        # Buat votes untuk pemilihan CLOSED (ada hasilnya)
        vote_data = [
            (voter_objects[0], cand_c1),
            (voter_objects[1], cand_c1),
            (voter_objects[2], cand_c1),
            (voter_objects[3], cand_c2),
            (voter_objects[4], cand_c2),
        ]
        for voter, candidate in vote_data:
            Vote.objects.get_or_create(
                voter=voter, election=election_closed,
                defaults={'candidate': candidate}
            )

        self.stdout.write(self.style.SUCCESS(
            f'Pemilihan CLOSED dibuat: "{election_closed.title}" '
            f'(5 suara: Paslon 1=3, Paslon 2=2)'
        ))

        # ── 5. Pemilihan 3: DRAFT (belum dibuka) ────────────────────────────
        election_draft, _ = Election.objects.get_or_create(
            title='Pemilihan Ketua UKM Robotika UI 2026',
            defaults={
                'description': (
                    'Pemilihan Ketua Unit Kegiatan Mahasiswa Robotika Universitas Indonesia '
                    'periode 2026-2027. Pemilihan akan dibuka setelah kandidat diverifikasi.'
                ),
                'start_date': now + timedelta(days=7),
                'end_date': now + timedelta(days=8),
                'status': Election.STATUS_DRAFT,
                'created_by': admin,
            }
        )
        Candidate.objects.get_or_create(
            election=election_draft, number=1,
            defaults={
                'name': 'Paslon INOVASI — Gilang Ramadhan & Putri Ayu',
                'vision': 'UKM Robotika sebagai pusat inovasi teknologi robotik mahasiswa UI.',
                'mission': (
                    '1. Membangun laboratorium robotik yang modern dan accessible\n'
                    '2. Kompetisi robotik nasional tahunan\n'
                    '3. Program magang di perusahaan otomasi industri\n'
                    '4. Publikasi riset robotik di jurnal internasional'
                ),
            }
        )
        Candidate.objects.get_or_create(
            election=election_draft, number=2,
            defaults={
                'name': 'Paslon TANGGUH — Hendra Wijaya & Claudia Santoso',
                'vision': 'Membangun tim robotik UI yang tangguh dan berdaya saing global.',
                'mission': (
                    '1. Training intensif pemrograman embedded system\n'
                    '2. Kerjasama dengan robotics club internasional\n'
                    '3. Pameran robotik terbuka untuk masyarakat umum\n'
                    '4. Beasiswa khusus bagi anggota berprestasi'
                ),
            }
        )

        self.stdout.write(self.style.SUCCESS(
            f'Pemilihan DRAFT dibuat: "{election_draft.title}"'
        ))

        # ── 6. Buat Akun Kandidat & Hubungkan ke Profil ─────────────────────
        election_map = {'draft': election_draft, 'open': election_open}
        for cu in CANDIDATE_USERS:
            cand_user, created = CustomUser.objects.get_or_create(
                email=cu['email'],
                defaults={
                    'username': cu['username'],
                    'first_name': cu['first_name'],
                    'last_name': cu['last_name'],
                    'role': CustomUser.ROLE_CANDIDATE,
                }
            )
            if created:
                cand_user.set_password(cu['password'])
                cand_user.save()
                self.stdout.write(self.style.SUCCESS(f'Kandidat user dibuat: {cu["email"]}'))
            else:
                self.stdout.write(f'Kandidat user sudah ada: {cu["email"]}')

            election_obj = election_map[cu['election_key']]
            try:
                candidate_obj = Candidate.objects.get(
                    election=election_obj, number=cu['candidate_number']
                )
                if candidate_obj.user != cand_user:
                    candidate_obj.user = cand_user
                    candidate_obj.save()
                    self.stdout.write(self.style.SUCCESS(
                        f'  -> Dihubungkan ke: {candidate_obj.name}'
                    ))
            except Candidate.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'  -> Kandidat tidak ditemukan untuk election={cu["election_key"]} '
                    f'nomor={cu["candidate_number"]}'
                ))

        # ── Ringkasan ────────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 55))
        self.stdout.write(self.style.SUCCESS('Seed data berhasil dibuat!'))
        self.stdout.write(self.style.SUCCESS('=' * 55))
        self.stdout.write('')
        self.stdout.write('AKUN TERSEDIA:')
        self.stdout.write(f'  Admin     -> {ADMIN_EMAIL} / {ADMIN_PASSWORD}')
        for v in VOTERS:
            self.stdout.write(f'  Pemilih   -> {v["email"]} / {v["password"]}')
        for cu in CANDIDATE_USERS:
            lock_info = 'bisa edit profil (DRAFT)' if cu['election_key'] == 'draft' else 'terkunci (OPEN)'
            self.stdout.write(f'  Kandidat  -> {cu["email"]} / {cu["password"]}  [{lock_info}]')
        self.stdout.write('')
        self.stdout.write('PEMILIHAN:')
        self.stdout.write(f'  OPEN   -> "{election_open.title}"')
        self.stdout.write(f'           (pemilih1 sudah vote, pemilih2-5 belum)')
        self.stdout.write(f'  CLOSED -> "{election_closed.title}"')
        self.stdout.write(f'           (5 suara masuk, hasil bisa dilihat)')
        self.stdout.write(f'  DRAFT  -> "{election_draft.title}"')
        self.stdout.write(f'           (belum dibuka, kandidat bisa edit visi/misi)')
        self.stdout.write('')
        self.stdout.write('Jalankan: python manage.py runserver')
        self.stdout.write('Akses   : http://127.0.0.1:8000/')
