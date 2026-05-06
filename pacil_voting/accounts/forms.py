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
        # TODO: Strip and lowercase the email, then validate with is_valid_email().
        # Raise ValidationError('Format email tidak valid.') if invalid.
        pass

    def clean_password(self):
        # TODO: Ensure password is not empty and does not exceed 128 characters.
        # Raise appropriate ValidationError for each case.
        pass


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
        # TODO: Strip and lowercase, validate with is_valid_email(), and check uniqueness.
        # Raise ValidationError if format is invalid or email already exists in the DB.
        pass

    def clean_first_name(self):
        # TODO: Sanitize with sanitize_text(), then validate against r'^[a-zA-Z\s\-\.]{1,50}$'.
        # Raise ValidationError if format doesn't match.
        pass

    def clean_last_name(self):
        # TODO: Sanitize with sanitize_text(). If non-empty, validate against r'^[a-zA-Z\s\-\.]{0,50}$'.
        # Last name is optional so allow blank.
        pass

    def clean_nim(self):
        # TODO: Strip the NIM value, then validate with is_valid_nim() if non-empty.
        pass

    def clean_username(self):
        # TODO: Strip username, validate against r'^[a-zA-Z0-9_\.]{3,30}$', and check uniqueness.
        pass

    def clean_password(self):
        # TODO: Run Django's built-in validate_password() on the password.
        # Let it raise ValidationError if the password is too weak.
        pass

    def clean(self):
        # TODO: Cross-field validation — confirm password == password_confirm.
        # Use self.add_error('password_confirm', ...) if they don't match.
        pass

    def save(self, commit=True):
        # TODO: Save the user with role=ROLE_PEMILIH and hashed password.
        # Use super().save(commit=False), set user.role, call user.set_password(), then save.
        pass
