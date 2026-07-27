from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

_ALLOWED_HOSTS = {
    "tiktok.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "facebook.com",
    "fb.watch",
}


def normalize_social_url(raw_url: str) -> str:
    value = raw_url.strip()
    if re.search(r"[\x00-\x1f\x7f]|%0[ad]", value, re.IGNORECASE):
        raise ValueError("URL contains control characters")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must use http or https")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL contains an invalid port") from exc
    if parsed.username or parsed.password or port:
        raise ValueError("URL credentials and custom ports are not allowed")

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or not any(
        host == allowed or host.endswith(f".{allowed}") for allowed in _ALLOWED_HOSTS
    ):
        raise ValueError("URL host is not a supported social platform")

    clean_path = parsed.path or "/"
    return urlunsplit(("https", host, clean_path, parsed.query, ""))
