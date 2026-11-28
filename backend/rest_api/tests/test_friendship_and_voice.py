"""Friend requests (the gate in front of every DM) and who may get a voice token.

A friend request is only the recipient's to answer, and accepting one is what
creates the DM. A voice token is only for a member of a callable channel: the
token is the whole of the SFU's authorization, so `join` is the check.
"""

import pytest
from jose import jwt
from libs.db import ChannelMember, ChannelType, FriendRequest, Friendship
from sqlalchemy import select
from src.core.config import settings
from src.friendship.service import FriendshipService
from src.utils.exceptions import (
    AlreadyExistsException,
    ForbiddenException,
    NotFoundException,
)
from src.voice import service as voice_service
from src.voice.service import VoiceService
from tests.service_db import run, side_effects, world  # noqa: F401


async def requested(w, sender, recipient):
    return await w.call(FriendshipService, "create_friend_request", sender, recipient.name)


def test_only_the_recipient_answers_a_friend_request(side_effects):
    async def scenario():
        async with world() as w:
            a, b, c = [await w.user(n) for n in "abc"]
            request = await requested(w, a, b)
            for someone in (a, c):
                with pytest.raises(NotFoundException):
                    await w.call(FriendshipService, "accept_friend_request", someone, request.id)
                with pytest.raises(NotFoundException):
                    await w.call(FriendshipService, "reject_friend_request", someone.id, request.id)
            assert await w.scalars(select(Friendship.user_1_id)) == []

    run(scenario())


def test_accepting_makes_friends_and_a_two_person_dm(side_effects):
    async def scenario():
        async with world() as w:
            a, b = await w.user("a"), await w.user("b")
            request = await requested(w, a, b)
            accepted = await w.call(FriendshipService, "accept_friend_request", b, request.id)
            assert accepted.friend_id == a.id
            members = await w.scalars(
                select(ChannelMember.user_id).where(
                    ChannelMember.channel_id == accepted.dm_channel_id
                )
            )
            assert {str(m) for m in members} == {a.id, b.id}
            assert await w.scalars(select(FriendRequest.id)) == []
            # A second request either way is refused now
            with pytest.raises(AlreadyExistsException):
                await requested(w, b, a)

    run(scenario())


def test_requests_cannot_be_duplicated_or_sent_to_yourself(side_effects):
    async def scenario():
        async with world() as w:
            a, b = await w.user("a"), await w.user("b")
            await requested(w, a, b)
            with pytest.raises(AlreadyExistsException):
                await requested(w, a, b)
            with pytest.raises(AlreadyExistsException):
                await requested(w, b, a)
            with pytest.raises(AlreadyExistsException):
                await requested(w, a, a)

    run(scenario())


# --------------------------------------------------------------------------
# Voice tokens
# --------------------------------------------------------------------------


class EmptyRoster:
    async def members(self, room):
        return []


@pytest.fixture()
def voice(monkeypatch):
    monkeypatch.setattr(voice_service, "voice_roster", EmptyRoster())
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", "test-secret-for-tokens")
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "test-key")


def test_a_voice_token_is_for_members_only(side_effects, voice):
    async def scenario():
        async with world() as w:
            owner, out = await w.user("owner"), await w.user("out")
            guild_id = await w.guild(owner)
            voice_channel = next(
                str(c.id) for c in await w.guild_channels(guild_id) if c.type == ChannelType.GUILD_VOICE
            )
            with pytest.raises(NotFoundException):
                await w.call(VoiceService, "join", out, voice_channel)
            with pytest.raises(NotFoundException):
                await w.call(VoiceService, "participants", out, voice_channel)

            joined = await w.call(VoiceService, "join", owner, voice_channel)
            claims = jwt.decode(
                joined.token, "test-secret-for-tokens", algorithms=["HS256"], options={"verify_aud": False}
            )
            # The token names this room and this person, nothing wider
            assert claims["video"]["room"] == voice_channel
            assert claims["sub"] == owner.id

    run(scenario())


def test_a_guild_text_channel_cannot_be_called(side_effects, voice):
    async def scenario():
        async with world() as w:
            owner = await w.user("owner")
            guild_id = await w.guild(owner)
            text = next(
                str(c.id) for c in await w.guild_channels(guild_id) if c.type == ChannelType.GUILD_TEXT
            )
            with pytest.raises(ForbiddenException):
                await w.call(VoiceService, "join", owner, text)

    run(scenario())


@pytest.mark.parametrize("kind", [ChannelType.DM, ChannelType.GROUP_DM])
def test_direct_conversations_can_be_called_by_their_members(side_effects, voice, kind):
    async def scenario():
        async with world() as w:
            a, b, c = [await w.user(n) for n in "abc"]
            channel = await w.channel(kind, a, b)
            assert (await w.call(VoiceService, "join", b, channel)).room == channel
            with pytest.raises(NotFoundException):
                await w.call(VoiceService, "join", c, channel)

    run(scenario())
