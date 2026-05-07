import hashlib
import json
from django.db import models
from django.conf import settings
from django.utils import timezone


class AuditLog(models.Model):
    ACTION_LOGIN = 'LOGIN'
    ACTION_LOGOUT = 'LOGOUT'
    ACTION_LOGIN_FAILED = 'LOGIN_FAILED'
    ACTION_ACCOUNT_LOCKED = 'ACCOUNT_LOCKED'
    ACTION_VOTE_CAST = 'VOTE_CAST'
    ACTION_ELECTION_CREATED = 'ELECTION_CREATED'
    ACTION_ELECTION_OPENED = 'ELECTION_OPENED'
    ACTION_ELECTION_CLOSED = 'ELECTION_CLOSED'
    ACTION_CANDIDATE_ADDED = 'CANDIDATE_ADDED'
    ACTION_CANDIDATE_UPDATED = 'CANDIDATE_UPDATED'
    ACTION_CANDIDATE_DELETED = 'CANDIDATE_DELETED'
    ACTION_USER_CREATED = 'USER_CREATED'

    ACTION_CHOICES = [
        (ACTION_LOGIN, 'Login'),
        (ACTION_LOGOUT, 'Logout'),
        (ACTION_LOGIN_FAILED, 'Login Gagal'),
        (ACTION_ACCOUNT_LOCKED, 'Akun Terkunci'),
        (ACTION_VOTE_CAST, 'Suara Diberikan'),
        (ACTION_ELECTION_CREATED, 'Pemilihan Dibuat/Diedit'),
        (ACTION_ELECTION_OPENED, 'Pemilihan Dibuka'),
        (ACTION_ELECTION_CLOSED, 'Pemilihan Ditutup'),
        (ACTION_CANDIDATE_ADDED, 'Kandidat Ditambahkan'),
        (ACTION_CANDIDATE_UPDATED, 'Kandidat Diperbarui'),
        (ACTION_CANDIDATE_DELETED, 'Kandidat Dihapus'),
        (ACTION_USER_CREATED, 'Pengguna Dibuat/Dihapus'),
    ]

    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs'
    )
    actor_email = models.EmailField(default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)
    log_hash = models.CharField(max_length=64, editable=False)

    class Meta:
        verbose_name = 'Log Audit'
        verbose_name_plural = 'Log Audit'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.action} - {self.actor_email}"

    def save(self, *args, **kwargs):
        if not self.log_hash:
            self.log_hash = self._compute_hash()
        super().save(*args, **kwargs)

    def _compute_hash(self):
        data = {
            'action': self.action,
            'actor_email': self.actor_email,
            'ip_address': str(self.ip_address) if self.ip_address else '',
            'details': self.details,
            'timestamp': timezone.now().isoformat(),
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    @classmethod
    def log(cls, action, actor=None, ip_address=None, details=None):
        return cls.objects.create(
            action=action,
            actor=actor,
            actor_email=actor.email if actor else '',
            ip_address=ip_address,
            details=details or {},
        )
