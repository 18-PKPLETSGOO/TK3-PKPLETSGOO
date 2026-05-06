from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Election
from .forms import ElectionForm
from accounts.decorators import admin_required
from accounts.utils import get_client_ip
from audit.models import AuditLog


@login_required
def election_list_view(request):
    # TODO: Fetch all elections and render 'elections/list.html'.
    pass


@login_required
def election_detail_view(request, pk):
    # TODO: Fetch election by pk (or 404).
    # Fetch its candidates.
    # For pemilih users, check if they have already voted (user_voted flag).
    # Render 'elections/detail.html' with election, candidates, user_voted.
    pass


@admin_required
def election_create_view(request):
    # TODO: GET → show blank ElectionForm.
    # POST → validate, set election.created_by = request.user, save.
    # Log ACTION_ELECTION_CREATED, show success message, redirect to elections:detail.
    pass


@admin_required
def election_edit_view(request, pk):
    # TODO: Fetch election (or 404). Block editing if status != DRAFT.
    # GET → show ElectionForm pre-filled with instance.
    # POST → validate and save. Log ACTION_ELECTION_CREATED (edit variant), redirect to detail.
    pass


@admin_required
def election_open_view(request, pk):
    # TODO: Fetch election (or 404).
    # GET → render 'elections/confirm_open.html'.
    # POST → validate that status == DRAFT and candidates.count() >= 2.
    # Set status to OPEN, save, log ACTION_ELECTION_OPENED, redirect to detail.
    pass


@admin_required
def election_close_view(request, pk):
    # TODO: Fetch election (or 404).
    # GET → render 'elections/confirm_close.html'.
    # POST → validate that status == OPEN.
    # Set status to CLOSED, save, log ACTION_ELECTION_CLOSED, redirect to detail.
    pass
