import re
from django import forms
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser
from .utils import sanitize_text, is_valid_email, is_valid_nim


class LoginForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email',
            'autocomplete': 'email',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
            'autocomplete': 'current-password',
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not is_valid_email(email):
            raise forms.ValidationError('Format email tidak valid.')
        return email


    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        if not password:
            raise forms.ValidationError('Password tidak boleh kosong.')
        if len(password) > 128:
            raise forms.ValidationError('Password terlalu panjang.')
        return password


class AddVoterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Password',
        help_text='Minimal 8 karakter, kombinasi huruf dan angka.'
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Konfirmasi Password'
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'first_name', 'last_name', 'nim', 'username']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'nim': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not is_valid_email(email):
            raise forms.ValidationError('Format email tidak valid.')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Email sudah terdaftar.')
        return email

    def clean_first_name(self):
        name = sanitize_text(self.cleaned_data.get('first_name', ''))
        if not re.match(r'^[a-zA-Z\s\-\.]{1,50}$', name):
            raise forms.ValidationError('Nama hanya boleh mengandung huruf, spasi, atau tanda hubung.')
        return name

    def clean_last_name(self):
        name = sanitize_text(self.cleaned_data.get('last_name', ''))
        if name and not re.match(r'^[a-zA-Z\s\-\.]{0,50}$', name):
            raise forms.ValidationError('Nama hanya boleh mengandung huruf, spasi, atau tanda hubung.')
        return name

    def clean_nim(self):
        nim = self.cleaned_data.get('nim', '').strip()
        if nim and not is_valid_nim(nim):
            raise forms.ValidationError('NIM hanya boleh mengandung huruf dan angka (5–20 karakter).')
        return nim

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not re.match(r'^[a-zA-Z0-9_\.]{3,30}$', username):
            raise forms.ValidationError('Username hanya boleh huruf, angka, titik, atau underscore (3–30 karakter).')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('Username sudah digunakan.')
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get('password')
        pw_confirm = cleaned_data.get('password_confirm')
        if pw and pw_confirm and pw != pw_confirm:
            self.add_error('password_confirm', 'Password tidak cocok.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = CustomUser.ROLE_PEMILIH
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class AddCandidateUserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Password',
        help_text='Minimal 8 karakter, kombinasi huruf dan angka.',
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Konfirmasi Password',
    )
    candidate = forms.ModelChoiceField(
        queryset=None,
        label='Data Kandidat',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Pilih data kandidat yang belum memiliki akun.',
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'first_name', 'last_name', 'username']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from candidates.models import Candidate
        self.fields['candidate'].queryset = Candidate.objects.filter(user__isnull=True).select_related('election')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not is_valid_email(email):
            raise forms.ValidationError('Format email tidak valid.')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Email sudah terdaftar.')
        return email

    def clean_first_name(self):
        name = sanitize_text(self.cleaned_data.get('first_name', ''))
        if not re.match(r'^[a-zA-Z\s\-\.]{1,50}$', name):
            raise forms.ValidationError('Nama hanya boleh mengandung huruf, spasi, atau tanda hubung.')
        return name

    def clean_last_name(self):
        name = sanitize_text(self.cleaned_data.get('last_name', ''))
        if name and not re.match(r'^[a-zA-Z\s\-\.]{0,50}$', name):
            raise forms.ValidationError('Nama hanya boleh mengandung huruf, spasi, atau tanda hubung.')
        return name

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not re.match(r'^[a-zA-Z0-9_\.]{3,30}$', username):
            raise forms.ValidationError('Username hanya boleh huruf, angka, titik, atau underscore (3–30 karakter).')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('Username sudah digunakan.')
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get('password')
        pw_confirm = cleaned_data.get('password_confirm')
        if pw and pw_confirm and pw != pw_confirm:
            self.add_error('password_confirm', 'Password tidak cocok.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = CustomUser.ROLE_CANDIDATE
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            candidate = self.cleaned_data['candidate']
            candidate.user = user
            candidate.save()
        return user
