from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status

from .config import Settings
from .downloader import MediaProcessor
from .models import JobResponse, JobStatusResponse, SendAsyncRequest, SendMessageRequest
from .security import normalize_social_url
from .service import JobService, QueueFullError
from .store import JobStore
from .telegram import TelegramClient


def create_app(
    *,
    settings: Settings | None = None,
    job_service: JobService | None = None,
    telegram: TelegramClient | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    telegram_client = telegram or TelegramClient(resolved.telegram_bot_token)
    service = job_service or JobService(
        JobStore(resolved.database_path),
        MediaProcessor(resolved, telegram_client),
        max_workers=resolved.max_workers,
        max_queue_size=resolved.max_queue_size,
        retention_days=resolved.job_retention_days,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        service.start()
        try:
            yield
        finally:
            service.stop()

    app = FastAPI(
        title="Telegram Social Video Downloader",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if x_api_key is None or not hmac.compare_digest(x_api_key, resolved.api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
            )

    auth = Depends(require_api_key)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/send_async",
        response_model=JobResponse,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[auth],
    )
    def send_async(request: SendAsyncRequest) -> JobResponse:
        try:
            url = normalize_social_url(request.url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            job, created = service.enqueue(
                request_id=request.request_id,
                chat_id=request.chat_id,
                url=url,
            )
        except QueueFullError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        return JobResponse(job_id=job.id, status=job.status, duplicate=not created)

    @app.get("/status/{job_id}", response_model=JobStatusResponse, dependencies=[auth])
    def job_status(job_id: str) -> JobStatusResponse:
        job = service.store.get(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
            )
        return JobStatusResponse(job_id=job.id, status=job.status, error=job.error)

    @app.post("/send_message", dependencies=[auth])
    def send_message(request: SendMessageRequest) -> dict[str, int | bool]:
        try:
            message_id = telegram_client.send_message(
                chat_id=request.chat_id, text=request.text
            )
        except RuntimeError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Telegram delivery failed",
            ) from None
        return {"ok": True, "message_id": message_id}

    return app
