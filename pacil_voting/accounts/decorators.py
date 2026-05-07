from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_role:
            messages.error(request, 'Akses ditolak. Halaman ini hanya untuk Admin.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped


def pemilih_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_pemilih_role:
            messages.error(request, 'Akses ditolak. Halaman ini hanya untuk Pemilih.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped


def login_not_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped
