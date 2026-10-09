from datetime import datetime

from pydantic import BaseModel, field_validator
from src.media.schemas import AttachmentResponse


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
    attachments: list[AttachmentResponse] = []

    @field_validator("id", "sender_id", "channel_id", mode="before")
    @classmethod
    def _as_str(cls, value):
        return str(value)
