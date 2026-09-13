from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_QUERY_SECRET_KEYS = {"api_token", "api-token", "api_key", "apikey", "access_token", "token"}
_HEADER_SECRET_KEYS = {"authorization", "x-rapidapi-key", "x-api-key", "api-key"}


def redact_text(value: str, secret: str | None = None) -> str:
    """Remove credentials from strings that may be logged or raised."""
    redacted = value
    if secret:
        redacted = redacted.replace(secret, "[redacted]")
    redacted = re.sub(r"(?i)(api_token=)[^&\s]+", r"\1[redacted]", redacted)
    redacted = re.sub(r"(?i)(apikey=)[^&\s]+", r"\1[redacted]", redacted)
    redacted = re.sub(r"(?i)(authorization:\s*)\S+", r"\1[redacted]", redacted)
    return redacted


def redact_url(url: str, secret: str | None = None) -> str:
    split = urlsplit(url)
    query = [
        (key, "[redacted]" if key.lower() in _QUERY_SECRET_KEYS else value)
        for key, value in parse_qsl(split.query, keep_blank_values=True)
    ]
    cleaned = urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))
    return redact_text(cleaned, secret)


def strip_secret_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in _HEADER_SECRET_KEYS}
