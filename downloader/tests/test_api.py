from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.main import create_app
from app.store import JobStore
from fastapi.testclient import TestClient


class FakeTelegram:
    def __init__(self, *, fail: bool = False) -> None:
        self.messages: list[tuple[str, str]] = []
        self.fail = fail

    def send_message(self, *, chat_id: str, text: str) -> int:
        if self.fail:
            raise RuntimeError("request contained a secret URL")
        self.messages.append((chat_id, text))
        return 99


class FakeService:
    def __init__(self, store: JobStore) -> None:
        self.store = store

    def start(self) -> None:
        self.store.initialize()

    def stop(self) -> None:
        pass

    def enqueue(self, *, request_id: str | None, chat_id: str, url: str):
        return self.store.create_or_get(request_id=request_id, chat_id=chat_id, url=url)


def make_client(
    tmp_path: Path, *, telegram_failure: bool = False
) -> tuple[TestClient, FakeTelegram]:
    settings = Settings(
        api_key="a" * 32,
        telegram_bot_token="123456:" + "b" * 24,
        database_path=tmp_path / "jobs.sqlite3",
    )
    store = JobStore(settings.database_path)
    service = FakeService(store)
    telegram = FakeTelegram(fail=telegram_failure)
    return TestClient(
        create_app(settings=settings, job_service=service, telegram=telegram)
    ), telegram


def test_health_does_not_require_credentials(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    with client:
        assert client.get("/healthz").json() == {"status": "ok"}


def test_send_async_requires_api_key_and_is_idempotent(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    payload = {
        "chat_id": "123",
        "url": "https://x.com/user/status/123",
        "request_id": "update-1",
    }
    with client:
        assert client.post("/send_async", json=payload).status_code == 401
        first = client.post(
            "/send_async", json=payload, headers={"X-API-Key": "a" * 32}
        )
        second = client.post(
            "/send_async", json=payload, headers={"X-API-Key": "a" * 32}
        )
    assert first.status_code == 202
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert second.json()["job_id"] == first.json()["job_id"]


def test_send_async_rejects_ssrf_target(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    with client:
        response = client.post(
            "/send_async",
            json={"chat_id": "123", "url": "http://127.0.0.1/private"},
            headers={"X-API-Key": "a" * 32},
        )
    assert response.status_code == 422


def test_send_message_uses_server_side_bot_client(tmp_path: Path) -> None:
    client, telegram = make_client(tmp_path)
    with client:
        response = client.post(
            "/send_message",
            json={"chat_id": "123", "text": "hello"},
            headers={"X-API-Key": "a" * 32},
        )
    assert response.json() == {"ok": True, "message_id": 99}
    assert telegram.messages == [("123", "hello")]


def test_send_message_redacts_telegram_transport_errors(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, telegram_failure=True)
    with client:
        response = client.post(
            "/send_message",
            json={"chat_id": "123", "text": "hello"},
            headers={"X-API-Key": "a" * 32},
        )
    assert response.status_code == 502
    assert response.json() == {"detail": "Telegram delivery failed"}
    assert "secret" not in response.text
