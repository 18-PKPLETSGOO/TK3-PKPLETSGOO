from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError, transaction

from .models import Vote
from .forms import VoteForm
from elections.models import Election
from accounts.decorators import pemilih_required
from accounts.utils import get_client_ip
from audit.models import AuditLog


@pemilih_required
def cast_vote_view(request, election_pk):
    # TODO: Fetch election (or 404).
    # Guard 1 — election not active: redirect to elections:detail with error.
    # Guard 2 — already voted (pre-check): redirect to voting:status with warning.
    #
    # GET → show VoteForm with election's candidates.
    #
    # POST → validate form, then inside transaction.atomic():
    #   - Re-check for existing vote using select_for_update() (race condition guard).
    #   - Re-fetch election with select_for_update() and verify still active.
    #   - Create Vote(voter, election, candidate).
    #   Catch IntegrityError (DB-level unique_together violation) and redirect to status.
    # On success: log ACTION_VOTE_CAST (include anonymous_token), show success, redirect to status.
    pass


@pemilih_required
def vote_status_view(request, election_pk):
    # TODO: Fetch election (or 404).
    # Fetch the user's Vote for this election (use .first(), may be None).
    # Render 'voting/status.html' with election and vote.
    pass
