from __future__ import annotations

from pydantic import BaseModel


class CopilotStatus(BaseModel):
    status: str
    message: str


class CopilotEvent(BaseModel):
    type: str
    text: str
    hint: str | None = None
    created_at: str
