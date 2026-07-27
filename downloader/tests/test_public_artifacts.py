from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "workflow" / "workflow.json"

SECRET_PATTERNS = [
    re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}", re.IGNORECASE),
    re.compile(r"n8n\.volyxai\.com", re.IGNORECASE),
    re.compile(r"X-Telegram-Bot-Token", re.IGNORECASE),
]


def test_workflow_is_inactive_and_secret_free() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    workflow = json.loads(raw)
    assert workflow["active"] is False
    assert len(workflow["nodes"]) == 7
    assert not any(pattern.search(raw) for pattern in SECRET_PATTERNS)
    assert workflow["id"] == "afd41696-99f8-4bea-a5b5-d15c47a50e27"
    assert "versionId" not in workflow
    assert "DOWNLOADER_API_URL" in raw
    assert "DOWNLOADER_API_KEY" in raw
    assert "TELEGRAM_WEBHOOK_SECRET" in raw
    assert "x-telegram-bot-api-secret-token" in raw.lower()
    parser = next(
        node for node in workflow["nodes"] if node["name"] == "Parse Telegram Update"
    )
    assert "new URL(url)" in parser["parameters"]["jsCode"]


def test_workflow_has_no_credential_references_or_live_telegram_urls() -> None:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    for node in workflow["nodes"]:
        assert "credentials" not in node
        serialized = json.dumps(node)
        assert "api.telegram.org/bot" not in serialized

    queue = next(node for node in workflow["nodes"] if node["name"] == "Queue Download")
    assert queue["parameters"]["method"] == "POST"
    assert "request_id" in queue["parameters"]["jsonBody"]
