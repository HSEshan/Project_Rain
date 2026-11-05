from datetime import datetime
from typing import Optional

from libs.db import MAX_MESSAGE_LENGTH
from pydantic import BaseModel, field_validator
from src.media.schemas import AttachmentResponse


class MessageEdit(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _clean(cls, value: str) -> str:
        # The socket's rules, see `build_client_event`: a NUL cannot be stored
        value = value.replace("\x00", "")
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Messages can be up to {MAX_MESSAGE_LENGTH} characters"
            )
        return value


class MessageResponse(BaseModel):
    """A message in a channel's history, with its images in composed order.

    Same shape the gateway delivers live (`metadata.attachments` on a message
    event carries these objects), so the client builds one `Message` from
    either source.
    """

    id: str
    content: str
    sender_id: str
    channel_id: str
    created_at: datetime
    edited_at: Optional[datetime] = None
    attachments: list[AttachmentResponse] = []

    @field_validator("id", "sender_id", "channel_id", mode="before")
    @classmethod
    def _as_str(cls, value):
        return str(value)
