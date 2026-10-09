from collections import defaultdict

from fastapi import Depends
from libs.db import Attachment, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.channel.repository import ChannelRepository
from src.database.core import get_db
from src.database.service import BaseService
from src.media.schemas import AttachmentResponse
from src.message.schemas import MessageResponse


class MessageService(BaseService):
    async def get_messages_by_channel_id(
        self, user: CurrentUser, channel_id: str
    ) -> list[MessageResponse]:
        await ChannelRepository.check_channel_member(self.db, user.id, channel_id)
        result = await self.db.execute(
            select(Message)
            .where(Message.channel_id == channel_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        # One query for every attachment in the page rather than one per
        # message. Most messages have none, so this is usually an empty result.
        by_message: dict[str, list[AttachmentResponse]] = defaultdict(list)
        if messages:
            attachments = await self.db.execute(
                select(Attachment)
                .where(Attachment.message_id.in_([m.id for m in messages]))
                .order_by(Attachment.position)
            )
            for row in attachments.scalars().all():
                by_message[str(row.message_id)].append(
                    AttachmentResponse.from_row(row)
                )

        return [
            MessageResponse(
                id=message.id,
                content=message.content,
                sender_id=message.sender_id,
                channel_id=message.channel_id,
                created_at=message.created_at,
                attachments=by_message.get(str(message.id), []),
            )
            for message in messages
        ]


def get_message_service(db: AsyncSession = Depends(get_db)) -> MessageService:
    return MessageService(db=db)
