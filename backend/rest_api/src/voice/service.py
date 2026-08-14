import structlog
from fastapi import Depends
from libs.db import Channel, ChannelType, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.channel.repository import ChannelRepository
from src.core.config import settings
from src.database.core import get_db
from src.database.service import BaseService
from src.realtime import events
from src.realtime.publisher import realtime_publisher
from src.utils.exceptions import (
    ForbiddenException,
    NotFoundException,
    ServiceUnavailableException,
)
from src.voice.roster import voice_roster
from src.voice.schemas import VoiceJoinResponse, VoiceParticipants
from src.voice.tokens import create_join_token

logger = structlog.get_logger()


class VoiceService(BaseService):
    """Joining a voice channel, and reacting to what the SFU reports.

    This service hands out a token and reads the roster. It does not write the
    roster: LiveKit does, through `handle_participant_change`. No audio passes
    through rest_api, the gateway, Redis or gRPC — the client talks to LiveKit
    directly once it has the token. Only presence uses our event pipeline,
    because people who are *not* in the room still need to see who is.
    """

    async def join(self, user: CurrentUser, channel_id: str) -> VoiceJoinResponse:
        if not settings.LIVEKIT_API_SECRET:
            raise ServiceUnavailableException(
                "Voice is not configured on this server (LIVEKIT_API_SECRET is unset)"
            )

        channel = await self._get_voice_channel(user, channel_id)

        # Room id is the channel id. There is no mapping table on purpose: the
        # channel already carries the membership that authorises the join, and
        # a second identifier would only be a thing to keep in sync.
        room = str(channel.id)
        token = create_join_token(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
            room=room,
            user_id=str(user.id),
            username=user.name,
        )

        # Deliberately no roster write here. A token is not a connection: the
        # client may never reach the SFU, and adding them now is exactly how
        # ghosts got into the list. The `participant_joined` webhook adds them
        # once they are actually in the room.
        return VoiceJoinResponse(
            room=room,
            token=token,
            url_path=settings.LIVEKIT_PUBLIC_PATH,
            identity=str(user.id),
            participants=await voice_roster.members(room),
        )

    async def participants(
        self, user: CurrentUser, channel_id: str
    ) -> VoiceParticipants:
        channel = await self._get_voice_channel(user, channel_id)
        room = str(channel.id)
        return VoiceParticipants(
            channel_id=room, participants=await voice_roster.members(room)
        )

    async def handle_participant_change(
        self, *, room: str, user_id: str, joined: bool
    ) -> None:
        """A LiveKit `participant_joined` / `participant_left` webhook.

        The room name is the channel id and the participant identity is the
        user id, both set when the token was minted, so nothing has to be
        looked up to route this — only the username, for the event text.
        """
        if joined:
            await voice_roster.add(room, user_id)
        else:
            await voice_roster.remove(room, user_id)

        username = await self._username(user_id)
        await realtime_publisher.publish(
            events.voice_state_changed(
                actor_id=user_id,
                actor_username=username,
                channel_id=room,
                joined=joined,
            )
        )
        logger.info(
            "Voice participant change", room=room, user_id=user_id, joined=joined
        )

    async def handle_room_started(self, *, room: str) -> None:
        """LiveKit created the room, so it holds nobody.

        Anything still in our set predates this room and is stale — a ghost
        left by a browser that died before webhooks existed. Clearing it here
        means a stale roster heals itself the next time anyone joins.
        """
        stale = await voice_roster.clear(room)
        if not stale:
            return

        logger.warning("Cleared stale voice roster", room=room, members=len(stale))
        for user_id in stale:
            await realtime_publisher.publish(
                events.voice_state_changed(
                    actor_id=user_id,
                    actor_username=await self._username(user_id),
                    channel_id=room,
                    joined=False,
                )
            )

    async def handle_room_finished(self, *, room: str) -> None:
        """Everyone has gone. Drop the key rather than leaving an empty set."""
        for user_id in await voice_roster.clear(room):
            await realtime_publisher.publish(
                events.voice_state_changed(
                    actor_id=user_id,
                    actor_username=await self._username(user_id),
                    channel_id=room,
                    joined=False,
                )
            )

    async def _username(self, user_id: str) -> str:
        result = await self.db.execute(select(User.username).where(User.id == user_id))
        return result.scalar_one_or_none() or "Someone"

    async def _get_voice_channel(self, user: CurrentUser, channel_id: str) -> Channel:
        # 404 rather than 403 when they are not a member: whether the channel
        # exists is itself privileged (see AGENTS.md)
        await ChannelRepository.check_channel_member(self.db, user.id, channel_id)

        result = await self.db.execute(select(Channel).where(Channel.id == channel_id))
        channel = result.scalar_one_or_none()
        if not channel:
            raise NotFoundException("Channel not found")
        if channel.type != ChannelType.GUILD_VOICE:
            # DM and group calls are explicitly out of scope for v1. They can
            # reuse these rooms later without any protocol change.
            raise ForbiddenException("This channel is not a voice channel")
        return channel


def get_voice_service(db: AsyncSession = Depends(get_db)):
    return VoiceService(db)
