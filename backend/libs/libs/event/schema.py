from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_id() -> str:
    return str(uuid4())


class EventType(str, Enum):
    MESSAGE = "message"
    CALL = "call"
    NOTIFICATION = "notification"
    FRIEND_REQUEST = "friend_request"


class Event(BaseModel):
    event_id: str = Field(default_factory=generate_id)
    event_type: EventType
    sender_id: str
    receiver_id: str
    text: str
    metadata: Optional[dict] = None
    timestamp: str = Field(default_factory=get_timestamp)

    @field_validator("sender_id", "receiver_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        try:
            UUID(v, version=4)
        except ValueError:
            raise ValueError(f"Invalid UUID: {v}")
        return v
    
    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except Exception:
            raise ValueError(f"Invalid ISO8601 timestamp: {v}")
        return v
