import re
import html


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')

def sanitize_text(value):
    if not value:
        return value
    return html.escape(str(value).strip())

def is_safe_text(value, max_length=500):
    if not value:
        return True
    pattern = r'^[\w\s\.,\-\(\)\!\?\:\;\"\'\&\/\+\=\@\#\%\^\*\[\]àáâãäåæçèéêëìíîïðñòóôõöùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞ]+$'
    return bool(re.match(pattern, value, re.UNICODE)) and len(value) <= max_length

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def is_valid_nim(nim):
    return bool(re.match(r'^[a-zA-Z0-9]{5,20}$', nim)) if nim else True
