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

    @classmethod
    def is_user_addressed(cls, event_type: "EventType | str") -> bool:
        """Whether `receiver_id` holds a user id rather than a channel id.

        Delivery differs by addressing: user-addressed events resolve through
        `user:{id}:grpc_endpoint`, channel-addressed ones through
        `channel:{id}:grpc_endpoints`. Keep this the only place that knows.
        """
        return cls(event_type) in USER_ADDRESSED_EVENT_TYPES


USER_ADDRESSED_EVENT_TYPES = frozenset(
    {EventType.NOTIFICATION, EventType.FRIEND_REQUEST}
)


class EventAction(str, Enum):
    """Values for `Event.metadata["action"]`.

    User-addressed events all look alike on the wire, so the action tells the
    gateway and the client what actually happened.
    """

    FRIEND_REQUEST_RECEIVED = "friend_request_received"
    FRIEND_REQUEST_ACCEPTED = "friend_request_accepted"
    GUILD_INVITE_RECEIVED = "guild_invite_received"
    # Nothing to show the user beyond "your channels changed"
    CHANNELS_CHANGED = "channels_changed"


# Metadata flag, set alongside any action that changed the recipient's channel
# membership. The gateway re-reads its mapping and the client refetches; the
# action says *what* happened, this says *what the receiver must reload*.
CHANNELS_CHANGED_FLAG = "channels_changed"


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
