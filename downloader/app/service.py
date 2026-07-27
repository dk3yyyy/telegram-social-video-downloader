from __future__ import annotations

import queue
import threading
from typing import Protocol

from .store import JobRecord, JobStore


class Processor(Protocol):
    def process(self, job: JobRecord) -> None: ...


class QueueFullError(RuntimeError):
    pass


class JobService:
    def __init__(
        self,
        store: JobStore,
        processor: Processor,
        *,
        max_workers: int,
        max_queue_size: int,
        retention_days: int = 7,
    ):
        self.store = store
        self.processor = processor
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=max_queue_size)
        self._max_workers = max_workers
        self._retention_days = retention_days
        self._workers: list[threading.Thread] = []
        self._started = False
        self._stopping = threading.Event()

    def start(self) -> None:
        if self._started:
            return
        self.store.initialize()
        self.store.delete_finished_older_than(self._retention_days)
        self._stopping.clear()
        self._started = True
        for index in range(self._max_workers):
            worker = threading.Thread(
                target=self._run, name=f"download-worker-{index + 1}", daemon=True
            )
            worker.start()
            self._workers.append(worker)
        for job in self.store.recover_pending():
            try:
                self._queue.put_nowait(job.id)
            except queue.Full:
                self.store.set_status(
                    job.id, "failed", "Queue capacity exceeded during recovery"
                )

    def stop(self) -> None:
        if not self._started:
            return
        self._stopping.set()
        for _ in self._workers:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                break
        for worker in self._workers:
            worker.join(timeout=1)
        self._workers.clear()
        self._started = False

    def enqueue(
        self, *, request_id: str | None, chat_id: str, url: str
    ) -> tuple[JobRecord, bool]:
        job, created = self.store.create_or_get(
            request_id=request_id, chat_id=chat_id, url=url
        )
        if not created:
            return job, False
        try:
            self._queue.put_nowait(job.id)
        except queue.Full as exc:
            # Admission failed, so remove the provisional row and let the same
            # request_id retry once queue capacity is available.
            self.store.delete(job.id)
            raise QueueFullError("Download queue is full") from exc
        return job, True

    def _run(self) -> None:
        while True:
            if self._stopping.is_set():
                return
            try:
                job_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if job_id is None:
                    return
                job = self.store.get(job_id)
                if job is None or job.status != "queued":
                    continue
                self.store.set_status(job.id, "running")
                try:
                    self.processor.process(job)
                # A third-party extractor or HTTP client must not terminate the worker.
                except Exception as exc:  # noqa: BLE001
                    self.store.set_status(job.id, "failed", _public_error(exc))
                else:
                    self.store.set_status(job.id, "succeeded")
            finally:
                self._queue.task_done()


def _public_error(exc: Exception) -> str:
    allowed = {
        "yt-dlp failed",
        "yt-dlp produced no supported media file",
        "ffprobe could not inspect downloaded media",
        "Downloaded file does not contain a usable video stream",
        "Downloaded video metadata is invalid",
        "Cannot calculate a safe transcode bitrate",
        "ffmpeg could not create a Telegram-compatible video",
        "Video remains above Telegram's configured upload limit",
        "Downloaded media exceeds the configured size limit",
        "Telegram rejected the request",
        "Telegram request failed",
        "Media tool timed out",
    }
    message = str(exc)
    if any(message.startswith(prefix) for prefix in allowed):
        return message[:500]
    return "Download or delivery failed"
