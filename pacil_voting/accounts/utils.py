import re
import html


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def sanitize_text(value):
    # TODO: Sanitize a text input for safe storage and display.
    # Return value unchanged if falsy.
    # Otherwise, strip leading/trailing whitespace and escape HTML special chars using html.escape().
    pass


def is_safe_text(value, max_length=500):
    # TODO: Return True if value only contains safe characters and is within max_length.
    # Return True for empty/None values (field is optional).
    # Safe character allowlist: alphanumeric, whitespace, common punctuation,
    # and accented Latin characters (àáâ...ÿ range).
    # Use re.match() with re.UNICODE flag.
    pass


def is_valid_email(email):
    # TODO: Return True if email matches a standard email format.
    # Use a regex: local part @ domain . tld
    pass


def is_valid_nim(nim):
    # TODO: Return True if nim is alphanumeric and between 5–20 characters.
    # Return True if nim is empty/None (NIM is optional).
    pass
