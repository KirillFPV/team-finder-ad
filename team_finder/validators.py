import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_github_url(value):
    if not value:
        return
    URLValidator(schemes=["http", "https"])(value)
    if urlsplit(value).hostname not in {"github.com", "www.github.com"}:
        raise ValidationError("Укажите ссылку на github.com.")


def normalize_phone(value):
    value = (value or "").strip()
    if not value:
        return None
    if not re.fullmatch(r"(?:8|\+7)[0-9]{10}", value):
        raise ValidationError("Введите телефон в формате 8XXXXXXXXXX или +7XXXXXXXXXX.")
    return "+7" + value[-10:]
