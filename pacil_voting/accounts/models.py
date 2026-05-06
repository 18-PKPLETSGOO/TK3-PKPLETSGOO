from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class CustomUser(AbstractUser):
    ROLE_ADMIN = 'ADMIN'
    ROLE_PEMILIH = 'PEMILIH'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_PEMILIH, 'Pemilih'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_PEMILIH)
    nim = models.CharField(max_length=20, blank=True, verbose_name='NIM')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'Pengguna'
        verbose_name_plural = 'Pengguna'

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.role})"

    @property
    def is_admin_role(self):
        # TODO: Return True if this user's role equals ROLE_ADMIN.
        pass

    @property
    def is_pemilih_role(self):
        # TODO: Return True if this user's role equals ROLE_PEMILIH.
        pass


class LoginAttempt(models.Model):
    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Percobaan Login'
        verbose_name_plural = 'Percobaan Login'
        indexes = [
            models.Index(fields=['email', 'timestamp']),
        ]

    def __str__(self):
        status = 'berhasil' if self.success else 'gagal'
        return f"{self.email} - {status} - {self.timestamp}"

    @classmethod
    def get_recent_failures(cls, email, minutes=15):
        # TODO: Count failed login attempts for `email` within the last `minutes` minutes.
        # Hint: use timezone.now() - timedelta(minutes=minutes) as the time window start.
        # Filter by success=False and timestamp__gte=window.
        pass

    @classmethod
    def is_locked_out(cls, email, max_attempts=5, minutes=15):
        # TODO: Return True if get_recent_failures(email, minutes) >= max_attempts.
        pass
