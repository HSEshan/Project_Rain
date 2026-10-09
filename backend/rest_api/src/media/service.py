"""Uploads: read within a limit, re-encode, store, record.

Avatars and guild icons live on their owner's row (`User.avatar_key`,
`Guild.icon_key`) and are handled by the user and guild services, which call
`store_image` here. Message attachments have a table of their own and are
handled entirely in this module, because an attachment exists before the
message that will carry it (see `libs.db.models.attachment`).
"""

import asyncio
from datetime import timedelta

import structlog
from fastapi import Depends, UploadFile
from libs.db import Attachment, generate_id, generate_timestamp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.core.config import settings
from src.database.core import get_db
from src.database.service import BaseService
from src.media.images import ImageKind, ProcessedImage, process_image
from src.media.schemas import AttachmentResponse
from src.media.storage import delete_quietly, get_storage
from src.utils.exceptions import PayloadTooLargeException

logger = structlog.get_logger()

# An upload nobody attached to a message within this long is abandoned: the
# composer was closed, the tab crashed, or the message it belonged to was
# deleted. Long enough that nobody loses an image they are still typing under.
ORPHAN_AFTER = timedelta(hours=1)
# How many orphans one sweep removes. The sweep runs inline on an upload, so it
# is bounded rather than allowed to turn one request into a cleanup job.
SWEEP_BATCH = 50

_READ_CHUNK = 64 * 1024


async def read_upload(upload: UploadFile) -> bytes:
    """The file's bytes, refusing as soon as it passes the limit.

    Read in chunks rather than all at once, so an oversized body is abandoned at
    the limit instead of being held in memory first. The edge has its own,
    slightly larger body limit; this is the one that produces a sentence.
    """
    limit = settings.MAX_UPLOAD_BYTES
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(_READ_CHUNK):
        size += len(chunk)
        if size > limit:
            raise PayloadTooLargeException(
                f"Images must be {limit // (1024 * 1024)} MB or smaller"
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def store_image(
    upload: UploadFile, kind: ImageKind, prefix: str
) -> tuple[str, ProcessedImage]:
    """Validate and store one image. Returns its new key and what was written.

    Stored *before* the caller's transaction commits, so a failed commit leaves
    an unreferenced object behind. That costs a few kilobytes; the opposite
    order would briefly reference an object that does not exist yet.
    """
    raw = await read_upload(upload)
    # Decoding and encoding is CPU work measured in tens of milliseconds for a
    # large photo; in the event loop it would stall every other request.
    image = await asyncio.to_thread(process_image, raw, kind)
    key = f"{prefix}/{generate_id()}.{image.extension}"
    await get_storage().put(key, image.data, image.content_type)
    return key, image


class MediaService(BaseService):
    async def upload_attachment(
        self, user: CurrentUser, upload: UploadFile
    ) -> AttachmentResponse:
        key, image = await store_image(
            upload, ImageKind.ATTACHMENT, f"attachments/{user.id}"
        )
        attachment = Attachment(
            id=generate_id(),
            uploader_id=user.id,
            key=key,
            content_type=image.content_type,
            size_bytes=len(image.data),
            width=image.width,
            height=image.height,
        )
        async with self.db.begin():
            self.db.add(attachment)

        await self.sweep_orphans()
        return AttachmentResponse.from_row(attachment)

    async def sweep_orphans(self) -> int:
        """Delete attachments that no message has claimed for an hour.

        Runs on every upload rather than on a schedule, because rest_api has no
        scheduler and does not need one for this: orphans are only created by
        people uploading, so the people uploading are enough to clear them. A
        quiet deployment keeps its last few orphans until someone uploads again,
        which is a bounded, harmless amount.

        Also where a deleted message's images end up (its attachments are set
        to null, not cascaded), so this is the single path by which any
        attachment object is ever removed.
        """
        cutoff = generate_timestamp(-ORPHAN_AFTER)
        async with self.db.begin():
            result = await self.db.execute(
                select(Attachment)
                .where(Attachment.message_id.is_(None), Attachment.created_at < cutoff)
                .limit(SWEEP_BATCH)
                # Two uploads sweeping at once must not both claim the same rows
                .with_for_update(skip_locked=True)
            )
            orphans = result.scalars().all()
            keys = [orphan.key for orphan in orphans]
            for orphan in orphans:
                await self.db.delete(orphan)

        if keys:
            await delete_quietly(keys)
            logger.info("Swept orphaned attachments", count=len(keys))
        return len(keys)


def get_media_service(db: AsyncSession = Depends(get_db)) -> MediaService:
    return MediaService(db)

