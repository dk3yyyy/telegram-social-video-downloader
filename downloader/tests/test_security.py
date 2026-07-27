from __future__ import annotations

import pytest
from app.security import normalize_social_url


@pytest.mark.parametrize(
    "url, expected_host",
    [
        ("https://www.tiktok.com/@creator/video/123", "www.tiktok.com"),
        ("https://vt.tiktok.com/abc", "vt.tiktok.com"),
        ("https://www.instagram.com/reel/abc/", "www.instagram.com"),
        ("https://x.com/user/status/123", "x.com"),
        ("https://twitter.com/user/status/123", "twitter.com"),
        ("https://fb.watch/abc/", "fb.watch"),
    ],
)
def test_normalize_supported_social_urls(url: str, expected_host: str) -> None:
    normalized = normalize_social_url(url)
    assert normalized.startswith(f"https://{expected_host}/")
    assert "#" not in normalized


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/video",
        "https://instagram.com.evil.example/video",
        "https://user:pass@x.com/video",  # pragma: allowlist secret
        "file:///etc/passwd",
        "https://example.com/video",
        "https://x.com:8443/video",
        "https://x.com:bad/video",
        "https://x.com/%0d%0aHost:evil",
    ],
)
def test_rejects_non_social_or_ambiguous_urls(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_social_url(url)
