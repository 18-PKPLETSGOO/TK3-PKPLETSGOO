from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import Candidate
from .forms import CandidateForm
from elections.models import Election
from accounts.decorators import admin_required
from accounts.utils import get_client_ip
from audit.models import AuditLog


@admin_required
def candidate_create_view(request, election_pk):
    # TODO: Fetch election by election_pk (or 404). Block if status != DRAFT.
    # GET → show blank CandidateForm.
    # POST → validate, set candidate.election = election, save.
    # Log ACTION_CANDIDATE_ADDED, show success message, redirect to elections:detail.
    pass


@admin_required
def candidate_edit_view(request, pk):
    # TODO: Fetch candidate by pk (or 404). Block if election.status != DRAFT.
    # GET → show CandidateForm pre-filled with instance.
    # POST → validate and save. Log ACTION_CANDIDATE_UPDATED, redirect to elections:detail.
    pass


@admin_required
def candidate_delete_view(request, pk):
    # TODO: Fetch candidate by pk (or 404). Block if election.status != DRAFT.
    # GET → render 'candidates/confirm_delete.html'.
    # POST → delete candidate, log ACTION_CANDIDATE_DELETED, redirect to elections:detail.
    pass
