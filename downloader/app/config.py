from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_BOT_TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{20,}$")


@dataclass(frozen=True, slots=True)
class Settings:
    api_key: str
    telegram_bot_token: str
    database_path: Path = Path("/data/jobs.sqlite3")
    max_workers: int = 2
    max_queue_size: int = 100
    job_timeout_seconds: int = 600
    max_download_bytes: int = 256 * 1024 * 1024
    max_duration_seconds: int = 1800
    job_retention_days: int = 7
    document_threshold_bytes: int = 20 * 1024 * 1024
    telegram_limit_bytes: int = 49 * 1024 * 1024

    @classmethod
    def from_env(cls) -> Settings:
        api_key = os.getenv("DOWNLOADER_API_KEY", "")
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if len(api_key) < 24:
            raise RuntimeError("DOWNLOADER_API_KEY must contain at least 24 characters")
        if not _BOT_TOKEN_RE.fullmatch(bot_token):
            raise RuntimeError("TELEGRAM_BOT_TOKEN has an invalid format")

        workers = _bounded_int("MAX_WORKERS", 2, minimum=1, maximum=8)
        queue_size = _bounded_int("MAX_QUEUE_SIZE", 100, minimum=1, maximum=10_000)
        timeout = _bounded_int("JOB_TIMEOUT_SECONDS", 600, minimum=30, maximum=3600)
        max_download_mib = _bounded_int(
            "MAX_DOWNLOAD_MIB", 256, minimum=10, maximum=900
        )
        max_duration = _bounded_int(
            "MAX_DURATION_SECONDS", 1800, minimum=10, maximum=14_400
        )
        retention_days = _bounded_int("JOB_RETENTION_DAYS", 7, minimum=1, maximum=365)
        return cls(
            api_key=api_key,
            telegram_bot_token=bot_token,
            database_path=Path(os.getenv("DATABASE_PATH", "/data/jobs.sqlite3")),
            max_workers=workers,
            max_queue_size=queue_size,
            job_timeout_seconds=timeout,
            max_download_bytes=max_download_mib * 1024 * 1024,
            max_duration_seconds=max_duration,
            job_retention_days=retention_days,
        )


def _bounded_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value
