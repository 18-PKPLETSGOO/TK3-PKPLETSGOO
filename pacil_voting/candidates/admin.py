from django.contrib import admin
from .models import Candidate


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'election')
    list_filter = ('election',)
    search_fields = ('name', 'election__title')
