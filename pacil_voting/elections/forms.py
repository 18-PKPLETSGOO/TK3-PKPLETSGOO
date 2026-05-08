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
        title = sanitize_text(self.cleaned_data.get('title', ''))
        if not title:
            raise forms.ValidationError('Judul pemilihan tidak boleh kosong.')
        if len(title) > 200:
            raise forms.ValidationError('Judul terlalu panjang (maks 200 karakter).')
        if re.search(r'[<>\{\}\|\\\^`]', title):
            raise forms.ValidationError('Judul mengandung karakter yang tidak diizinkan.')
        return title

    def clean_description(self):
        desc = sanitize_text(self.cleaned_data.get('description', ''))
        if len(desc) > 2000:
            raise forms.ValidationError('Deskripsi terlalu panjang (maks 2000 karakter).')
        return desc


    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and start >= end:
            raise forms.ValidationError('Tanggal mulai harus sebelum tanggal selesai.')
        return cleaned_data

