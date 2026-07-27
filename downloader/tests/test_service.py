from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest
from app.service import JobService, QueueFullError
from app.store import JobRecord, JobStore


class RecordingProcessor:
    def __init__(self) -> None:
        self.jobs: list[str] = []

    def process(self, job: JobRecord) -> None:
        self.jobs.append(job.id)


class BlockingProcessor:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def process(self, job: JobRecord) -> None:
        self.started.set()
        self.release.wait(timeout=3)


def wait_for_status(store: JobStore, job_id: str, expected: str) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        current = store.get(job_id)
        if current is not None and current.status == expected:
            return
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach {expected}")


def test_service_processes_and_deduplicates_jobs(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    processor = RecordingProcessor()
    service = JobService(store, processor, max_workers=1, max_queue_size=4)
    service.start()
    try:
        first, created = service.enqueue(
            request_id="telegram-update-42",
            chat_id="123",
            url="https://x.com/user/status/1",
        )
        assert created is True
        wait_for_status(store, first.id, "succeeded")

        duplicate, created_again = service.enqueue(
            request_id="telegram-update-42",
            chat_id="123",
            url="https://x.com/user/status/1",
        )
        assert created_again is False
        assert duplicate.id == first.id
        assert processor.jobs == [first.id]
    finally:
        service.stop()


def test_running_jobs_are_recovered_after_restart(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    job, _ = store.create_or_get(
        request_id="recover-me", chat_id="123", url="https://x.com/a/status/2"
    )
    store.set_status(job.id, "running")

    processor = RecordingProcessor()
    service = JobService(store, processor, max_workers=1, max_queue_size=4)
    service.start()
    try:
        wait_for_status(store, job.id, "succeeded")
        assert processor.jobs == [job.id]
    finally:
        service.stop()


def test_stop_does_not_block_on_a_full_queue(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    processor = BlockingProcessor()
    service = JobService(store, processor, max_workers=1, max_queue_size=1)
    service.start()
    try:
        service.enqueue(request_id="one", chat_id="123", url="https://x.com/a/status/1")
        assert processor.started.wait(timeout=1)
        service.enqueue(request_id="two", chat_id="123", url="https://x.com/a/status/2")
        started = time.monotonic()
        service.stop()
        assert time.monotonic() - started < 1.5
    finally:
        processor.release.set()


def test_finished_job_retention_cleanup(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    store.initialize()
    job, _ = store.create_or_get(
        request_id="expired", chat_id="123", url="https://x.com/a/status/3"
    )
    store.set_status(job.id, "succeeded")
    with sqlite3.connect(path) as db:
        db.execute("UPDATE jobs SET updated_at = '2000-01-01T00:00:00+00:00'")

    assert store.delete_finished_older_than(7) == 1
    assert store.get(job.id) is None


def test_queue_full_request_id_can_be_retried(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    processor = BlockingProcessor()
    service = JobService(store, processor, max_workers=1, max_queue_size=1)
    service.start()
    try:
        service.enqueue(request_id="one", chat_id="123", url="https://x.com/a/status/1")
        assert processor.started.wait(timeout=1)
        service.enqueue(request_id="two", chat_id="123", url="https://x.com/a/status/2")
        with pytest.raises(QueueFullError):
            service.enqueue(
                request_id="retryable", chat_id="123", url="https://x.com/a/status/3"
            )
        assert store.get_by_request_id("retryable") is None
    finally:
        processor.release.set()
        service.stop()
