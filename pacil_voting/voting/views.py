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
    election = get_object_or_404(Election, pk=election_pk)

    if not election.is_active:
        messages.error(request, 'Pemilihan tidak sedang aktif atau sudah berakhir.')
        return redirect('elections:detail', pk=election_pk)

    if Vote.objects.filter(voter=request.user, election=election).exists():
        messages.warning(request, 'Anda sudah memberikan suara pada pemilihan ini.')
        return redirect('voting:status', election_pk=election_pk)

    if request.method == 'POST':
        form = VoteForm(election, request.POST)
        if form.is_valid():
            candidate = form.cleaned_data['candidate']
            try:
                with transaction.atomic():
                    if Vote.objects.select_for_update().filter(
                        voter=request.user, election=election
                    ).exists():
                        messages.error(request, 'Anda sudah memberikan suara.')
                        return redirect('voting:status', election_pk=election_pk)

                    election_fresh = Election.objects.select_for_update().get(pk=election_pk)
                    if not election_fresh.is_active:
                        messages.error(request, 'Pemilihan telah berakhir.')
                        return redirect('elections:detail', pk=election_pk)

                    vote = Vote.objects.create(
                        voter=request.user,
                        election=election,
                        candidate=candidate,
                    )

                AuditLog.log(
                    action=AuditLog.ACTION_VOTE_CAST,
                    actor=request.user,
                    ip_address=get_client_ip(request),
                    details={
                        'election_id': election.pk,
                        'anonymous_token': vote.anonymous_token,
                    }
                )
                messages.success(request, 'Suara Anda berhasil dicatat.')
                return redirect('voting:status', election_pk=election_pk)

            except IntegrityError:
                messages.error(request, 'Anda sudah memberikan suara pada pemilihan ini.')
                return redirect('voting:status', election_pk=election_pk)
        else:
            messages.error(request, 'Silakan pilih salah satu kandidat.')
    else:
        form = VoteForm(election)

    return render(request, 'voting/cast.html', {
        'election': election,
        'form': form,
        'candidates': election.candidates.order_by('number'),
    })

@pemilih_required
def vote_status_view(request, election_pk):
    election = get_object_or_404(Election, pk=election_pk)
    vote = Vote.objects.filter(voter=request.user, election=election).first()
    return render(request, 'voting/status.html', {'election': election, 'vote': vote})

