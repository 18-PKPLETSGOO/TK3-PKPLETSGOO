from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        # TODO: Enforce admin-only access.
        # 1. If user is not authenticated → redirect to 'accounts:login'.
        # 2. If authenticated but not is_admin_role → add error message and redirect to 'home'.
        # 3. Otherwise → call and return view_func(request, *args, **kwargs).
        pass
    return _wrapped


def pemilih_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        # TODO: Enforce pemilih-only access.
        # 1. If user is not authenticated → redirect to 'accounts:login'.
        # 2. If authenticated but not is_pemilih_role → add error message and redirect to 'home'.
        # 3. Otherwise → call and return view_func(request, *args, **kwargs).
        pass
    return _wrapped


def login_not_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        # TODO: Redirect already-authenticated users away from guest-only pages (e.g. login page).
        # If user is authenticated → redirect to 'home'.
        # Otherwise → call and return view_func(request, *args, **kwargs).
        pass
    return _wrapped
