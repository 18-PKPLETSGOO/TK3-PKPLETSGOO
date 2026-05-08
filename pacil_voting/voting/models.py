import uuid
import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone
from elections.models import Election
from candidates.models import Candidate


class Vote(models.Model):
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='votes', verbose_name='Pemilih'
    )
    election = models.ForeignKey(
        Election, on_delete=models.CASCADE,
        related_name='votes', verbose_name='Pemilihan'
    )
    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE,
        related_name='votes', verbose_name='Kandidat'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    anonymous_token = models.CharField(max_length=64, unique=True, editable=False)

    class Meta:
        verbose_name = 'Suara'
        verbose_name_plural = 'Suara'
        unique_together = ('voter', 'election')

    def __str__(self):
        return f"Suara [{self.election}] - {self.timestamp}"

    def save(self, *args, **kwargs):
        if not self.anonymous_token:
            raw = f"{uuid.uuid4()}{self.voter_id}{self.election_id}{timezone.now().isoformat()}"
            self.anonymous_token = hashlib.sha256(raw.encode()).hexdigest()
        super().save(*args, **kwargs)

