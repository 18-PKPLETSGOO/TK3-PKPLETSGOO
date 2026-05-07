from django import forms
from candidates.models import Candidate


class VoteForm(forms.Form):
    candidate = forms.ModelChoiceField(
        queryset=Candidate.objects.none(),
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        empty_label=None,
        label='Pilih Kandidat',
        error_messages={'required': 'Silakan pilih salah satu kandidat.'}
    )

    def __init__(self, election, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['candidate'].queryset = Candidate.objects.filter(
            election=election
        ).order_by('number')
        self.election = election

    def clean_candidate(self):
        candidate = self.cleaned_data.get('candidate')
        if candidate and candidate.election != self.election:
            raise forms.ValidationError('Kandidat tidak valid untuk pemilihan ini.')
        return candidate

