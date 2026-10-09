from libs.db import Attachment
from libs.media import media_url
from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    """One image, as a message or the uploader sees it.

    Carries a URL and never the key. The key is an implementation detail of
    whichever storage backend is running; the URL is the only thing a client
    can use, and it is the same shape on every backend.
    """

    id: str
    url: str
    content_type: str
    width: int
    height: int
    size_bytes: int

    @classmethod
    def from_row(cls, row: Attachment) -> "AttachmentResponse":
        return cls(
            id=str(row.id),
            url=media_url(row.key),
            content_type=row.content_type,
            width=row.width,
            height=row.height,
            size_bytes=row.size_bytes,
        )
