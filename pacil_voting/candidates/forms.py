import re
from django import forms
from .models import Candidate
from accounts.utils import sanitize_text


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['number', 'name', 'vision', 'mission']
        widgets = {
            'number': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '99'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '200'}),
            'vision': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'maxlength': '2000'}),
            'mission': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'maxlength': '3000'}),
        }

    def clean_number(self):
        # TODO: Validate that number is between 1 and 99 (inclusive).
        pass

    def clean_name(self):
        # TODO: Sanitize with sanitize_text(), ensure non-empty and <= 200 chars.
        # Reject names containing: < > { } | \ ^ `
        pass

    def clean_vision(self):
        # TODO: Sanitize with sanitize_text(), ensure non-empty and <= 2000 chars.
        pass

    def clean_mission(self):
        # TODO: Sanitize with sanitize_text(), ensure non-empty and <= 3000 chars.
        pass
