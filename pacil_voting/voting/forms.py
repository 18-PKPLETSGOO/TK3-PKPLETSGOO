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
        # TODO: Set self.fields['candidate'].queryset to candidates belonging to `election`,
        # ordered by number. Store election as self.election for use in clean_candidate().
        pass

    def clean_candidate(self):
        # TODO: Validate that the chosen candidate actually belongs to self.election.
        # This prevents a user from submitting a candidate ID from a different election.
        # Raise ValidationError('Kandidat tidak valid untuk pemilihan ini.') if mismatch.
        pass
