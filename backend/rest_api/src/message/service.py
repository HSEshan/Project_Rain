from collections import defaultdict

from fastapi import Depends
from datetime import datetime, timezone

from libs.db import Attachment, Channel, Message
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.channel.repository import ChannelRepository
from src.database.core import get_db
from src.database.service import BaseService
from src.guild.permissions import GuildPermission, outranks
from src.guild.repository import GuildRepository
from src.media.schemas import AttachmentResponse
from src.media.storage import delete_quietly
from src.message.schemas import MessageEdit, MessageResponse
from src.realtime import events
from src.realtime.publisher import realtime_publisher
from src.utils.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)


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
                edited_at=message.edited_at,
                attachments=by_message.get(str(message.id), []),
            )
            for message in messages
        ]

    async def _visible_message(self, user: CurrentUser, message_id: str) -> Message:
        """The message, for a member of its channel. Callers hold the transaction.

        404 either way for anyone else: whether a message exists is the channel's
        business, the same rule as the channel itself.
        """
        result = await self.db.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if not message:
            raise NotFoundException("Message not found")
        await ChannelRepository.check_channel_member(
            self.db, user.id, str(message.channel_id)
        )
        return message

    async def edit_message(
        self, user: CurrentUser, message_id: str, edit: MessageEdit
    ) -> MessageResponse:
        async with self.db.begin():
            message = await self._visible_message(user, message_id)
            if str(message.sender_id) != str(user.id):
                raise ForbiddenException("You can only edit your own messages")

            attachments = await self.db.execute(
                select(Attachment)
                .where(Attachment.message_id == message.id)
                .order_by(Attachment.position)
            )
            attachments = attachments.scalars().all()
            # The rule at the socket: a message needs text or an image. Removing
            # the words from a captioned image is fine, emptying a text message
            # is what delete is for.
            if not edit.content.strip() and not attachments:
                raise BadRequestException("A message cannot be empty")

            message.content = edit.content
            message.edited_at = datetime.now(timezone.utc)
            await self.db.flush()
            response = MessageResponse(
                id=message.id,
                content=message.content,
                sender_id=message.sender_id,
                channel_id=message.channel_id,
                created_at=message.created_at,
                edited_at=message.edited_at,
                attachments=[AttachmentResponse.from_row(row) for row in attachments],
            )

        await realtime_publisher.publish(
            events.message_edited(
                actor_id=user.id,
                channel_id=response.channel_id,
                message_id=response.id,
                text=response.content,
                edited_at=response.edited_at.isoformat(),
            )
        )
        return response

    async def delete_message(self, user: CurrentUser, message_id: str) -> None:
        """Remove the message and its images, now.

        Not left to the sweep, as images under a deleted *channel* are. The sweep
        runs only on an upload and only after an hour, and someone deleting one
        message, a moderator above all, means that image and expects it gone. Its
        URL is public to anyone who has it.
        """
        async with self.db.begin():
            message = await self._visible_message(user, message_id)
            if str(message.sender_id) != str(user.id):
                await self._require_moderation(user, message)
            channel_id = str(message.channel_id)
            keys = await self.db.execute(
                delete(Attachment)
                .where(Attachment.message_id == message.id)
                .returning(Attachment.key)
            )
            keys = list(keys.scalars().all())
            await self.db.delete(message)

        await delete_quietly(keys)
        await realtime_publisher.publish(
            events.message_deleted(
                actor_id=user.id, channel_id=channel_id, message_id=message_id
            )
        )

    async def _require_moderation(self, user: CurrentUser, message: Message) -> None:
        """Someone else's message, in a guild, by someone who outranks its author.

        A DM or a group DM has no hierarchy to appeal to, so there it is your own or
        nothing. An author who has left the guild has no standing, so anyone with
        the permission can tidy up after them.
        """
        channel = await self.db.execute(
            select(Channel.guild_id).where(Channel.id == message.channel_id)
        )
        guild_id = channel.scalar_one()
        if guild_id is None:
            raise ForbiddenException("You can only delete your own messages")
        guild_id = str(guild_id)

        actor = await GuildRepository.require_permission(
            self.db, guild_id, user.id, GuildPermission.MANAGE_MESSAGES
        )
        author = await GuildRepository.get_standing(
            self.db, guild_id, str(message.sender_id)
        )
        if author is not None and not outranks(actor, author):
            raise ForbiddenException(
                "You can only delete messages from people below you in this guild"
            )


def get_message_service(db: AsyncSession = Depends(get_db)) -> MessageService:
    return MessageService(db=db)
