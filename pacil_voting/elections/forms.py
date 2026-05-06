import re
from django import forms
from .models import Election
from accounts.utils import sanitize_text


class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ['title', 'description', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '200'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'maxlength': '2000'}),
            'start_date': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'end_date': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_date'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean_title(self):
        # TODO: Sanitize with sanitize_text(), ensure non-empty and <= 200 chars.
        # Reject titles containing any of: < > { } | \ ^ `
        pass

    def clean_description(self):
        # TODO: Sanitize with sanitize_text(), ensure <= 2000 chars.
        pass

    def clean(self):
        # TODO: Cross-field validation — ensure start_date < end_date.
        # Raise ValidationError on the form (not a field) if the order is wrong.
        pass
