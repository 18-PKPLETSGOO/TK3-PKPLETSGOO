from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.conf import settings

from .models import CustomUser, LoginAttempt
from .forms import LoginForm, AddVoterForm
from .decorators import admin_required, login_not_required
from .utils import get_client_ip
from audit.models import AuditLog


@login_not_required
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        ip = get_client_ip(request)

        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
            lockout_minutes = getattr(settings, 'LOCKOUT_DURATION_MINUTES', 15)

            # TODO: Check if the account is locked out using LoginAttempt.is_locked_out().
            # If locked: log ACTION_ACCOUNT_LOCKED, show lockout error message, re-render form.

            # TODO: Authenticate the user with Django's authenticate().
            # On success: call login(), record a successful LoginAttempt, log ACTION_LOGIN,
            #             redirect to 'home'.
            # On failure: record a failed LoginAttempt, log ACTION_LOGIN_FAILED,
            #             calculate remaining attempts and show an appropriate error message.
            pass
        else:
            messages.error(request, 'Input tidak valid. Periksa kembali data Anda.')

        return render(request, 'accounts/login.html', {'form': form})

    form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    # TODO: If user is authenticated, log ACTION_LOGOUT with AuditLog.log().
    # Call logout(request) and request.session.flush() to clear the session.
    # Show a success message and redirect to 'accounts:login'.
    pass


@admin_required
def voter_list_view(request):
    # TODO: Fetch all users with role=ROLE_PEMILIH ordered by email.
    # Render 'accounts/voter_list.html' with the queryset.
    pass


@admin_required
def add_voter_view(request):
    # TODO: Handle GET (show blank AddVoterForm) and POST (validate, save, log, redirect).
    # On success: log ACTION_USER_CREATED, show success message, redirect to 'accounts:voter_list'.
    # On failure: show error message and re-render the form.
    pass


@admin_required
def delete_voter_view(request, pk):
    # TODO: Fetch voter by pk (role=ROLE_PEMILIH only, else 404).
    # GET: render 'accounts/confirm_delete_voter.html'.
    # POST: delete voter, log ACTION_USER_CREATED (delete variant), show success, redirect to voter_list.
    pass
