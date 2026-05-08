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
        number = self.cleaned_data.get('number')
        if number is None or number < 1 or number > 99:
            raise forms.ValidationError('Nomor urut harus antara 1 dan 99.')
        return number

    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        if re.search(r'<[^>]+>', name):
            raise forms.ValidationError(
                'Input mengandung karakter tidak diizinkan (tag HTML/script tidak diperbolehkan).'
            )
        name = sanitize_text(name)
        if not name:
            raise forms.ValidationError('Nama paslon tidak boleh kosong.')
        if len(name) > 200:
            raise forms.ValidationError('Nama terlalu panjang (maks 200 karakter).')
        if re.search(r'[<>\{\}\|\\\^`]', name):
            raise forms.ValidationError('Nama mengandung karakter yang tidak diizinkan.')
        return name

    def clean_vision(self):
        vision = self.cleaned_data.get('vision', '')
        if re.search(r'<[^>]+>', vision):
            raise forms.ValidationError(
                'Input mengandung karakter tidak diizinkan (tag HTML/script tidak diperbolehkan).'
            )
        vision = sanitize_text(vision)
        if not vision:
            raise forms.ValidationError('Visi tidak boleh kosong.')
        if len(vision) > 2000:
            raise forms.ValidationError('Visi terlalu panjang (maks 2000 karakter).')
        return vision

    def clean_mission(self):
        mission = self.cleaned_data.get('mission', '')
        if re.search(r'<[^>]+>', mission):
            raise forms.ValidationError(
                'Input mengandung karakter tidak diizinkan (tag HTML/script tidak diperbolehkan).'
            )
        mission = sanitize_text(mission)
        if not mission:
            raise forms.ValidationError('Misi tidak boleh kosong.')
        if len(mission) > 3000:
            raise forms.ValidationError('Misi terlalu panjang (maks 3000 karakter).')
        return mission


class CandidateProfileForm(forms.ModelForm):
    """Form untuk kandidat mengedit visi & misi milik sendiri."""

    class Meta:
        model = Candidate
        fields = ['vision', 'mission']
        widgets = {
            'vision': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'maxlength': '2000',
                'placeholder': 'Tuliskan visi Anda...',
            }),
            'mission': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 7,
                'maxlength': '3000',
                'placeholder': 'Tuliskan misi Anda...',
            }),
        }

    def clean_vision(self):
        vision = self.cleaned_data.get('vision', '')
        if re.search(r'<[^>]+>', vision):
            raise forms.ValidationError(
                'Input mengandung karakter tidak diizinkan (tag HTML/script tidak diperbolehkan).'
            )
        vision = sanitize_text(vision)
        if not vision:
            raise forms.ValidationError('Visi tidak boleh kosong.')
        if len(vision) > 2000:
            raise forms.ValidationError('Visi terlalu panjang (maks 2000 karakter).')
        return vision

    def clean_mission(self):
        mission = self.cleaned_data.get('mission', '')
        if re.search(r'<[^>]+>', mission):
            raise forms.ValidationError(
                'Input mengandung karakter tidak diizinkan (tag HTML/script tidak diperbolehkan).'
            )
        mission = sanitize_text(mission)
        if not mission:
            raise forms.ValidationError('Misi tidak boleh kosong.')
        if len(mission) > 3000:
            raise forms.ValidationError('Misi terlalu panjang (maks 3000 karakter).')
        return mission

