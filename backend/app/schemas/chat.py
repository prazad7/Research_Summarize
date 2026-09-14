from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import ChatRole


class ChatMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatMessageOut(BaseModel):
    id: str
    role: ChatRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
