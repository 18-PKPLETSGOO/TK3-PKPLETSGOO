from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.conf import settings

from .models import CustomUser, LoginAttempt
from .forms import LoginForm, AddVoterForm, AddCandidateUserForm
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

            if LoginAttempt.is_locked_out(email, max_attempts, lockout_minutes):
                AuditLog.log(
                    action=AuditLog.ACTION_ACCOUNT_LOCKED,
                    ip_address=ip,
                    details={'email': email, 'reason': 'Too many failed attempts'}
                )
                messages.error(
                    request,
                    'Terlalu banyak percobaan login. Silakan coba lagi nanti.'
                )
                return render(request, 'accounts/login.html', {'form': form})

            user = authenticate(request, username=email, password=password)

            if user is not None:
                login(request, user)
                LoginAttempt.objects.create(email=email, ip_address=ip, success=True)
                AuditLog.log(
                    action=AuditLog.ACTION_LOGIN,
                    actor=user,
                    ip_address=ip
                )
                return redirect('home')
            else:
                LoginAttempt.objects.create(email=email, ip_address=ip, success=False)
                AuditLog.log(
                    action=AuditLog.ACTION_LOGIN_FAILED,
                    ip_address=ip,
                    details={'email': email}
                )
                if LoginAttempt.is_locked_out(email, max_attempts, lockout_minutes):
                    messages.error(
                        request,
                        'Terlalu banyak percobaan login. Silakan coba lagi nanti.'
                    )
                else:
                    messages.error(
                        request,
                        'Email atau password tidak valid.'
                    )
        else:
            messages.error(request, 'Input tidak valid. Periksa kembali data Anda.')

        return render(request, 'accounts/login.html', {'form': form})

    form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    if request.user.is_authenticated:
        AuditLog.log(
            action=AuditLog.ACTION_LOGOUT,
            actor=request.user,
            ip_address=get_client_ip(request)
        )
    logout(request)
    request.session.flush()
    messages.success(request, 'Anda berhasil logout.')
    return redirect('accounts:login')


@admin_required
def voter_list_view(request):
    voters = CustomUser.objects.filter(role=CustomUser.ROLE_PEMILIH).order_by('email')
    return render(request, 'accounts/voter_list.html', {'voters': voters})

@admin_required
def add_voter_view(request):
    if request.method == 'POST':
        form = AddVoterForm(request.POST)
        if form.is_valid():
            user = form.save()
            AuditLog.log(
                action=AuditLog.ACTION_USER_CREATED,
                actor=request.user,
                ip_address=get_client_ip(request),
                details={'new_user_email': user.email}
            )
            messages.success(request, f'Pemilih {user.email} berhasil ditambahkan.')
            return redirect('accounts:voter_list')
        else:
            messages.error(request, 'Terdapat kesalahan pada form. Periksa kembali.')
    else:
        form = AddVoterForm()
    return render(request, 'accounts/add_voter.html', {'form': form})

@admin_required
def delete_voter_view(request, pk):
    voter = get_object_or_404(CustomUser, pk=pk, role=CustomUser.ROLE_PEMILIH)
    if request.method == 'POST':
        email = voter.email
        voter.delete()
        AuditLog.log(
            action=AuditLog.ACTION_USER_CREATED,
            actor=request.user,
            ip_address=get_client_ip(request),
            details={'deleted_user_email': email, 'action': 'delete'}
        )
        messages.success(request, f'Pemilih {email} berhasil dihapus.')
        return redirect('accounts:voter_list')
    return render(request, 'accounts/confirm_delete_voter.html', {'voter': voter})


@admin_required
def candidate_user_list_view(request):
    candidates = CustomUser.objects.filter(role=CustomUser.ROLE_CANDIDATE).order_by('email')
    return render(request, 'accounts/candidate_user_list.html', {'candidates': candidates})


@admin_required
def add_candidate_user_view(request):
    if request.method == 'POST':
        form = AddCandidateUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            AuditLog.log(
                action=AuditLog.ACTION_USER_CREATED,
                actor=request.user,
                ip_address=get_client_ip(request),
                details={'new_user_email': user.email, 'role': CustomUser.ROLE_CANDIDATE},
            )
            messages.success(request, f'Akun kandidat {user.email} berhasil dibuat dan dihubungkan.')
            return redirect('accounts:candidate_user_list')
        else:
            messages.error(request, 'Terdapat kesalahan pada form. Periksa kembali.')
    else:
        form = AddCandidateUserForm()
    return render(request, 'accounts/add_candidate_user.html', {'form': form})