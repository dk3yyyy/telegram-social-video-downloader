from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_CHAT_ID_RE = re.compile(r"^-?\d{1,20}$")


class SendAsyncRequest(BaseModel):
    chat_id: str
    url: str = Field(min_length=10, max_length=2048)
    request_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id(cls, value: str) -> str:
        value = str(value).strip()
        if not _CHAT_ID_RE.fullmatch(value):
            raise ValueError("chat_id must be a Telegram numeric chat identifier")
        return value


class SendMessageRequest(BaseModel):
    chat_id: str
    text: str = Field(min_length=1, max_length=4096)

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id(cls, value: str) -> str:
        value = str(value).strip()
        if not _CHAT_ID_RE.fullmatch(value):
            raise ValueError("chat_id must be a Telegram numeric chat identifier")
        return value


class JobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    duplicate: bool = False


class JobStatusResponse(JobResponse):
    error: str | None = None
