from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import AuditLog
from elections.models import Election
from accounts.decorators import admin_required


@admin_required
def audit_log_view(request):
    logs = AuditLog.objects.select_related('actor').all()[:200]
    return render(request, 'audit/logs.html', {'logs': logs})


@login_required
def results_view(request, election_pk):
    election = get_object_or_404(Election, pk=election_pk)

    if request.user.is_pemilih_role and election.status != Election.STATUS_CLOSED:
        messages.info(request, 'Hasil akan tersedia setelah pemilihan ditutup.')
        return render(request, 'audit/results_pending.html', {'election': election})

    candidates = election.candidates.all().order_by('number')
    total_votes = election.votes.count()

    results = []
    for candidate in candidates:
        count = candidate.votes.count()
        percentage = round((count / total_votes * 100), 2) if total_votes > 0 else 0
        results.append({'candidate': candidate, 'count': count, 'percentage': percentage})

    results.sort(key=lambda x: x['count'], reverse=True)

    return render(request, 'audit/results.html', {
        'election': election,
        'results': results,
        'total_votes': total_votes,
    })