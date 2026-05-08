from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import Candidate
from .forms import CandidateForm, CandidateProfileForm
from elections.models import Election
from accounts.decorators import admin_required, candidate_required
from accounts.utils import get_client_ip
from audit.models import AuditLog


@admin_required
def candidate_create_view(request, election_pk):
    election = get_object_or_404(Election, pk=election_pk)
    if election.status != Election.STATUS_DRAFT:
        messages.error(request, 'Kandidat hanya dapat ditambahkan pada pemilihan berstatus Draft.')
        return redirect('elections:detail', pk=election_pk)

    if request.method == 'POST':
        form = CandidateForm(request.POST)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.election = election
            candidate.save()
            AuditLog.log(
                action=AuditLog.ACTION_CANDIDATE_ADDED,
                actor=request.user,
                ip_address=get_client_ip(request),
                details={
                    'election_id': election.pk,
                    'candidate_name': candidate.name,
                    'candidate_number': candidate.number,
                }
            )
            messages.success(request, f'Kandidat "{candidate.name}" berhasil ditambahkan.')
            return redirect('elections:detail', pk=election_pk)
        else:
            messages.error(request, 'Terdapat kesalahan pada form. Periksa kembali.')
    else:
        form = CandidateForm()
    return render(request, 'candidates/create.html', {'form': form, 'election': election})

@admin_required
def candidate_edit_view(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    election = candidate.election
    if election.status != Election.STATUS_DRAFT:
        messages.error(request, 'Kandidat hanya dapat diedit pada pemilihan berstatus Draft.')
        return redirect('elections:detail', pk=election.pk)

    if request.method == 'POST':
        form = CandidateForm(request.POST, instance=candidate)
        if form.is_valid():
            form.save()
            AuditLog.log(
                action=AuditLog.ACTION_CANDIDATE_UPDATED,
                actor=request.user,
                ip_address=get_client_ip(request),
                details={'candidate_id': candidate.pk, 'name': candidate.name}
            )
            messages.success(request, 'Kandidat berhasil diperbarui.')
            return redirect('elections:detail', pk=election.pk)
        else:
            messages.error(request, 'Terdapat kesalahan pada form.')
    else:
        form = CandidateForm(instance=candidate)
    return render(request, 'candidates/edit.html', {
        'form': form, 'candidate': candidate, 'election': election,
    })


@admin_required
def candidate_delete_view(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    election = candidate.election
    if election.status != Election.STATUS_DRAFT:
        messages.error(request, 'Kandidat hanya dapat dihapus pada pemilihan berstatus Draft.')
        return redirect('elections:detail', pk=election.pk)

    if request.method == 'POST':
        name = candidate.name
        election_pk = election.pk
        candidate.delete()
        AuditLog.log(
            action=AuditLog.ACTION_CANDIDATE_DELETED,
            actor=request.user,
            ip_address=get_client_ip(request),
            details={'candidate_name': name, 'election_id': election_pk}
        )
        messages.success(request, f'Kandidat "{name}" berhasil dihapus.')
        return redirect('elections:detail', pk=election_pk)
    return render(request, 'candidates/confirm_delete.html', {
        'candidate': candidate, 'election': election,
    })


@candidate_required
def candidate_edit_profile_view(request):
    try:
        candidate = request.user.candidate_profile
    except Candidate.DoesNotExist:
        messages.error(request, 'Akun Anda belum terhubung dengan data kandidat. Hubungi administrator.')
        return redirect('home')

    election = candidate.election
    locked = election.status != Election.STATUS_DRAFT

    if request.method == 'POST':
        if locked:
            messages.error(request, 'Profil tidak dapat diedit saat pemilihan bukan berstatus Draft.')
            return redirect('candidates:my_profile')

        form = CandidateProfileForm(request.POST, instance=candidate)
        if form.is_valid():
            form.save()
            AuditLog.log(
                action=AuditLog.ACTION_CANDIDATE_UPDATED,
                actor=request.user,
                ip_address=get_client_ip(request),
                details={'candidate_id': candidate.pk, 'name': candidate.name},
            )
            messages.success(request, 'Visi dan Misi berhasil diperbarui.')
            return redirect('candidates:my_profile')
        else:
            messages.error(request, 'Terdapat kesalahan pada form. Periksa kembali.')
    else:
        form = CandidateProfileForm(instance=candidate)

    return render(request, 'candidates/edit_profile.html', {
        'form': form,
        'candidate': candidate,
        'election': election,
        'locked': locked,
    })
