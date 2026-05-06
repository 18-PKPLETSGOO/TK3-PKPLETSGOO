from django.db import models
from elections.models import Election


class Candidate(models.Model):
    election = models.ForeignKey(
        Election, on_delete=models.CASCADE, related_name='candidates',
        verbose_name='Pemilihan'
    )
    number = models.PositiveIntegerField(verbose_name='Nomor Urut')
    name = models.CharField(max_length=200, verbose_name='Nama Paslon')
    vision = models.TextField(verbose_name='Visi')
    mission = models.TextField(verbose_name='Misi')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kandidat'
        verbose_name_plural = 'Kandidat'
        unique_together = ('election', 'number')
        ordering = ['number']

    def __str__(self):
        return f"Paslon {self.number} - {self.name}"

    def get_vote_count(self):
        return self.votes.count()
