from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.channel.repository import ChannelRepository
from src.database.core import get_db
from src.database.service import BaseService
from src.message.models import Message


class MessageService(BaseService):
    async def get_messages_by_channel_id(
        self, user: CurrentUser, channel_id: str
    ) -> list[Message]:
        await ChannelRepository.check_channel_member(self.db, user.id, channel_id)
        result = await self.db.execute(
            select(Message).where(Message.channel_id == channel_id)
        )
        return result.scalars().all()


def get_message_service(db: AsyncSession = Depends(get_db)) -> MessageService:
    return MessageService(db=db)
