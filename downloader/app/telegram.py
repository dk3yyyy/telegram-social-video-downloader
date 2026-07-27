from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

# Telegram Bot API credentials are part of the URL path. Suppress httpx's
# request-level INFO logging so a permissive root logger cannot expose them.
logging.getLogger("httpx").setLevel(logging.WARNING)


class TelegramClient:
    def __init__(self, bot_token: str, *, timeout_seconds: float = 120):
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._timeout = timeout_seconds

    def send_message(self, *, chat_id: str, text: str) -> int:
        payload = self._post("sendMessage", data={"chat_id": chat_id, "text": text})
        return int(payload["result"]["message_id"])

    def send_document(self, *, chat_id: str, path: Path) -> int:
        with path.open("rb") as media:
            payload = self._post(
                "sendDocument",
                data={"chat_id": chat_id, "disable_content_type_detection": "true"},
                files={"document": (path.name, media, "video/mp4")},
            )
        return int(payload["result"]["message_id"])

    def send_video(
        self, *, chat_id: str, path: Path, width: int, height: int, duration: int
    ) -> int:
        with path.open("rb") as media:
            payload = self._post(
                "sendVideo",
                data={
                    "chat_id": chat_id,
                    "width": str(width),
                    "height": str(height),
                    "duration": str(duration),
                    "supports_streaming": "true",
                },
                files={"video": (path.name, media, "video/mp4")},
            )
        return int(payload["result"]["message_id"])

    def _post(self, method: str, **kwargs: Any) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
                response = client.post(f"{self._base_url}/{method}", **kwargs)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            # Transport exceptions can contain Telegram's token-bearing URL.
            raise RuntimeError("Telegram request failed") from None
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise RuntimeError("Telegram rejected the request")
        return payload
