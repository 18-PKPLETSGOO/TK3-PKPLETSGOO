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
    elections = Election.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        elections = elections.filter(title__icontains=q)
    return render(request, 'elections/list.html', {'elections': elections, 'q': q})
    


@login_required
def election_detail_view(request, pk):
    election = get_object_or_404(Election, pk=pk)
    candidates = election.candidates.all()
    user_voted = False
    if request.user.is_pemilih_role:
        user_voted = election.votes.filter(voter=request.user).exists()
    return render(request, 'elections/detail.html', {
        'election': election,
        'candidates': candidates,
        'user_voted': user_voted,
    })


@admin_required
def election_create_view(request):
    if request.method == 'POST':
        form = ElectionForm(request.POST)
        if form.is_valid():
            election = form.save(commit=False)
            election.created_by = request.user
            election.save()
            AuditLog.log(
                action=AuditLog.ACTION_ELECTION_CREATED,
                actor=request.user,
                ip_address=get_client_ip(request),
                details={'election_id': election.pk, 'title': election.title}
            )
            messages.success(request, f'Pemilihan "{election.title}" berhasil dibuat.')
            return redirect('elections:detail', pk=election.pk)
        else:
            messages.error(request, 'Terdapat kesalahan pada form. Periksa kembali.')
    else:
        form = ElectionForm()
    return render(request, 'elections/create.html', {'form': form})



@admin_required
def election_edit_view(request, pk):
    election = get_object_or_404(Election, pk=pk)
    if election.status != Election.STATUS_DRAFT:
        messages.error(request, 'Pemilihan yang sudah dibuka atau ditutup tidak dapat diedit.')
        return redirect('elections:detail', pk=pk)
    if request.method == 'POST':
        form = ElectionForm(request.POST, instance=election)
        if form.is_valid():
            form.save()
            AuditLog.log(
                action=AuditLog.ACTION_ELECTION_CREATED,
                actor=request.user,
                ip_address=get_client_ip(request),
                details={'election_id': election.pk, 'action': 'edit'}
            )
            messages.success(request, 'Pemilihan berhasil diperbarui.')
            return redirect('elections:detail', pk=pk)
        else:
            messages.error(request, 'Terdapat kesalahan pada form.')
    else:
        form = ElectionForm(instance=election)
    return render(request, 'elections/edit.html', {'form': form, 'election': election})



@admin_required
def election_open_view(request, pk):
    election = get_object_or_404(Election, pk=pk)
    if request.method == 'POST':
        if election.status != Election.STATUS_DRAFT:
            messages.error(request, 'Hanya pemilihan berstatus Draft yang dapat dibuka.')
        elif election.candidates.count() < 2:
            messages.error(request, 'Minimal 2 kandidat diperlukan untuk membuka pemilihan.')
        else:
            election.status = Election.STATUS_OPEN
            election.save()
            AuditLog.log(
                action=AuditLog.ACTION_ELECTION_OPENED,
                actor=request.user,
                ip_address=get_client_ip(request),
                details={'election_id': election.pk, 'title': election.title}
            )
            messages.success(request, f'Pemilihan "{election.title}" berhasil dibuka.')
        return redirect('elections:detail', pk=pk)
    return render(request, 'elections/confirm_open.html', {'election': election})



@admin_required
def election_close_view(request, pk):
    election = get_object_or_404(Election, pk=pk)
    if request.method == 'POST':
        if election.status != Election.STATUS_OPEN:
            messages.error(request, 'Hanya pemilihan yang sedang berlangsung yang dapat ditutup.')
        else:
            election.status = Election.STATUS_CLOSED
            election.save()
            AuditLog.log(
                action=AuditLog.ACTION_ELECTION_CLOSED,
                actor=request.user,
                ip_address=get_client_ip(request),
                details={'election_id': election.pk, 'title': election.title}
            )
            messages.success(request, f'Pemilihan "{election.title}" berhasil ditutup.')
        return redirect('elections:detail', pk=pk)
    return render(request, 'elections/confirm_close.html', {'election': election})
