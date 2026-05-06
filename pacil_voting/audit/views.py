from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import AuditLog
from elections.models import Election
from accounts.decorators import admin_required


@admin_required
def audit_log_view(request):
    # TODO: Fetch the 200 most recent AuditLog entries using select_related('actor').
    # Render 'audit/logs.html' with the queryset as 'logs'.
    pass


@login_required
def results_view(request, election_pk):
    # TODO: Fetch election (or 404).
    # If user is pemilih and election is not CLOSED:
    #   show info message and render 'audit/results_pending.html'.
    # Otherwise:
    #   For each candidate, count votes and calculate percentage of total.
    #   Sort results by vote count descending.
    #   Render 'audit/results.html' with election, results list, and total_votes.
    #
    # results list format: [{'candidate': <obj>, 'count': int, 'percentage': float}, ...]
    pass
