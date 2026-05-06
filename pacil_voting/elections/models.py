from django.db import models
from django.conf import settings
from django.utils import timezone


class Election(models.Model):
    STATUS_DRAFT = 'DRAFT'
    STATUS_OPEN = 'OPEN'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_OPEN, 'Berlangsung'),
        (STATUS_CLOSED, 'Selesai'),
    ]

    title = models.CharField(max_length=200, verbose_name='Judul Pemilihan')
    description = models.TextField(blank=True, verbose_name='Deskripsi')
    start_date = models.DateTimeField(verbose_name='Tanggal Mulai')
    end_date = models.DateTimeField(verbose_name='Tanggal Selesai')
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT,
        verbose_name='Status'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_elections'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pemilihan'
        verbose_name_plural = 'Pemilihan'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN

    @property
    def is_active(self):
        now = timezone.now()
        return (
            self.status == self.STATUS_OPEN
            and self.start_date <= now <= self.end_date
        )

    def get_vote_count(self):
        return self.votes.count()
