from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: str
    request_id: str | None
    chat_id: str
    url: str
    status: str
    error: str | None
    created_at: str
    updated_at: str


class JobStore:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    request_id TEXT UNIQUE,
                    chat_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status)")

    def create_or_get(
        self, *, request_id: str | None, chat_id: str, url: str
    ) -> tuple[JobRecord, bool]:
        now = _now()
        job_id = str(uuid.uuid4())
        try:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO jobs (id, request_id, chat_id, url, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'queued', ?, ?)",
                    (job_id, request_id, chat_id, url, now, now),
                )
        except sqlite3.IntegrityError:
            if request_id is None:
                raise
            existing = self.get_by_request_id(request_id)
            if existing is None:
                raise
            return existing, False
        created = self.get(job_id)
        if created is None:
            raise RuntimeError("Created job could not be read back")
        return created, True

    def get(self, job_id: str) -> JobRecord | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _record(row)

    def get_by_request_id(self, request_id: str) -> JobRecord | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE request_id = ?", (request_id,)
            ).fetchone()
        return _record(row)

    def set_status(self, job_id: str, status: str, error: str | None = None) -> None:
        safe_error = error[:500] if error else None
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (status, safe_error, _now(), job_id),
            )

    def delete(self, job_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def recover_pending(self) -> list[JobRecord]:
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status = 'queued', updated_at = ? WHERE status = 'running'",
                (_now(),),
            )
            rows = db.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at"
            ).fetchall()
        return [_record(row) for row in rows if row is not None]

    def delete_finished_older_than(self, days: int) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM jobs WHERE status IN ('succeeded', 'failed') AND updated_at < ?",
                (cutoff,),
            )
            return cursor.rowcount

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db


def _record(row: sqlite3.Row | None) -> JobRecord | None:
    return JobRecord(**dict(row)) if row is not None else None


def _now() -> str:
    return datetime.now(UTC).isoformat()
