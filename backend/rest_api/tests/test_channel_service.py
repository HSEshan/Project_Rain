"""Who may see, create, join and leave channels.

Group DMs have no roles, so their one safety rule is "you can only add your own
friends". Guild channels go through the guild policy. Reads of a channel are for
its members, and a bulk read leaves out what is not yours rather than refusing.
"""

import pytest
from libs.db import (
    MAX_GROUP_DM_MEMBERS,
    Channel,
    ChannelMember,
    ChannelType,
    GuildMemberRole,
    Message,
    generate_id,
)
from sqlalchemy import select
from src.channel.schemas import (
    DMChannelCreate,
    GroupDMCreate,
    GroupDMMemberAdd,
    GroupDMUpdate,
    GuildChannelCreate,
)
from src.channel.service import ChannelService
from src.utils.exceptions import (
    AlreadyExistsException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from tests.service_db import run, side_effects, world  # noqa: F401


async def members_of(w, channel_id) -> set[str]:
    rows = await w.scalars(
        select(ChannelMember.user_id).where(ChannelMember.channel_id == channel_id)
    )
    return {str(r) for r in rows}


async def owner_of(w, channel_id):
    value = await w.scalar(select(Channel.owner_id).where(Channel.id == channel_id))
    return str(value) if value else None


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def test_a_channel_is_visible_to_its_members_only(side_effects):
    async def scenario():
        async with world() as w:
            a, b, c = [await w.user(n) for n in "abc"]
            dm = await w.channel(ChannelType.DM, a, b)
            with pytest.raises(NotFoundException):
                await w.call(ChannelService, "get_channel_by_id", c, dm)
            with pytest.raises(NotFoundException):
                await w.call(ChannelService, "get_channel_members", c, dm)
            channel = await w.call(ChannelService, "get_channel_by_id", b, dm)
            assert str(channel.id) == dm

    run(scenario())


def test_bulk_participants_leaves_out_channels_you_are_not_in(side_effects):
    async def scenario():
        async with world() as w:
            a, b, c, d = [await w.user(n) for n in "abcd"]
            mine = await w.channel(ChannelType.DM, a, b)
            theirs = await w.channel(ChannelType.DM, c, d)
            result = await w.call(ChannelService, "get_channel_participants", a, [mine, theirs])
            result = {str(k): [str(u) for u in v] for k, v in result.items()}
            assert result == {mine: [b.id]}

    run(scenario())


# --------------------------------------------------------------------------
# Direct messages
# --------------------------------------------------------------------------


def test_cannot_create_a_dm_between_two_other_people(side_effects):
    async def scenario():
        async with world() as w:
            a, b, c = [await w.user(n) for n in "abc"]
            await w.friends(b, c)
            with pytest.raises(ForbiddenException):
                await w.call(
                    ChannelService, "create_dm_channel", a, DMChannelCreate(user_id=b.id, user_id2=c.id)
                )

    run(scenario())


def test_a_dm_needs_a_friendship(side_effects):
    # The websocket only checks channel membership, so a DM with a stranger
    # would let them message anyone whose id they know.
    async def scenario():
        async with world() as w:
            a, stranger = await w.user("a"), await w.user("stranger")
            for pair in (
                DMChannelCreate(user_id=stranger.id, user_id2=a.id),
                DMChannelCreate(user_id=a.id, user_id2=stranger.id),
            ):
                with pytest.raises(ForbiddenException):
                    await w.call(ChannelService, "create_dm_channel", stranger, pair)
            assert not await w.scalars(
                select(Channel.id).where(Channel.type == ChannelType.DM)
            )

    run(scenario())


def test_friends_can_open_a_dm(side_effects):
    async def scenario():
        async with world() as w:
            a, b = await w.user("a"), await w.user("b")
            await w.friends(a, b)
            channel = await w.call(
                ChannelService, "create_dm_channel", b, DMChannelCreate(user_id=a.id, user_id2=b.id)
            )
            assert channel.type == ChannelType.DM
            assert await members_of(w, channel.id) == {a.id, b.id}

    run(scenario())


def test_cannot_open_a_dm_with_yourself(side_effects):
    async def scenario():
        async with world() as w:
            a = await w.user("a")
            with pytest.raises(BadRequestException):
                await w.call(
                    ChannelService, "create_dm_channel", a, DMChannelCreate(user_id=a.id, user_id2=a.id)
                )

    run(scenario())


# --------------------------------------------------------------------------
# Group DMs
# --------------------------------------------------------------------------


async def friends_of(w, me, *names):
    people = [await w.user(n) for n in names]
    for person in people:
        await w.friends(me, person)
    return people


def test_a_group_can_only_be_made_of_your_friends(side_effects):
    async def scenario():
        async with world() as w:
            me = await w.user("me")
            f1, f2 = await friends_of(w, me, "f1", "f2")
            stranger = await w.user("stranger")
            with pytest.raises(ForbiddenException):
                await w.call(
                    ChannelService, "create_group_dm", me, GroupDMCreate(user_ids=[f1.id, stranger.id])
                )
            assert await w.scalars(select(Channel.id)) == []

            channel = await w.call(
                ChannelService, "create_group_dm", me, GroupDMCreate(user_ids=[f1.id, f2.id])
            )
            assert await members_of(w, channel.id) == {me.id, f1.id, f2.id}
            assert str(channel.owner_id) == me.id

    run(scenario())


def test_the_creator_cannot_list_themselves_and_duplicates_are_refused(side_effects):
    async def scenario():
        async with world() as w:
            me = await w.user("me")
            (f1,) = await friends_of(w, me, "f1")
            with pytest.raises(BadRequestException):
                await w.call(
                    ChannelService, "create_group_dm", me, GroupDMCreate(user_ids=[f1.id, me.id])
                )
            with pytest.raises(ValueError):
                GroupDMCreate(user_ids=[f1.id, f1.id])
            with pytest.raises(ValueError):
                GroupDMCreate(user_ids=[f1.id])  # that is a DM
            with pytest.raises(ValueError):
                GroupDMCreate(user_ids=[generate_id() for _ in range(MAX_GROUP_DM_MEMBERS)])

    run(scenario())


def test_adding_needs_membership_and_friendship(side_effects):
    async def scenario():
        async with world() as w:
            me = await w.user("me")
            f1, f2, f3 = await friends_of(w, me, "f1", "f2", "f3")
            group = await w.channel(ChannelType.GROUP_DM, me, f1, f2)
            stranger = await w.user("stranger")

            # f1 is in the group but is not friends with f3
            with pytest.raises(ForbiddenException):
                await w.call(ChannelService, "add_group_dm_member", f1, group, GroupDMMemberAdd(user_id=f3.id))
            # f3 is not in the group at all
            with pytest.raises(NotFoundException):
                await w.call(ChannelService, "add_group_dm_member", f3, group, GroupDMMemberAdd(user_id=f3.id))
            with pytest.raises(ForbiddenException):
                await w.call(
                    ChannelService, "add_group_dm_member", me, group, GroupDMMemberAdd(user_id=stranger.id)
                )
            with pytest.raises(AlreadyExistsException):
                await w.call(ChannelService, "add_group_dm_member", me, group, GroupDMMemberAdd(user_id=f1.id))

            roster = await w.call(
                ChannelService, "add_group_dm_member", me, group, GroupDMMemberAdd(user_id=f3.id)
            )
            assert {m.user_id for m in roster.members} == {me.id, f1.id, f2.id, f3.id}
            assert f3.id in side_effects.invalidated

    run(scenario())


def test_a_group_is_capped(side_effects):
    async def scenario():
        async with world() as w:
            me = await w.user("me")
            friends = await friends_of(w, me, *[f"f{i}" for i in range(MAX_GROUP_DM_MEMBERS)])
            group = await w.channel(ChannelType.GROUP_DM, me, *friends[: MAX_GROUP_DM_MEMBERS - 1])
            with pytest.raises(BadRequestException):
                await w.call(
                    ChannelService, "add_group_dm_member", me, group, GroupDMMemberAdd(user_id=friends[-1].id)
                )
            assert len(await members_of(w, group)) == MAX_GROUP_DM_MEMBERS

    run(scenario())


def test_group_operations_refuse_other_channel_kinds(side_effects):
    async def scenario():
        async with world() as w:
            me = await w.user("me")
            (f1,) = await friends_of(w, me, "f1")
            dm = await w.channel(ChannelType.DM, me, f1)
            with pytest.raises(ForbiddenException):
                await w.call(ChannelService, "update_group_dm", me, dm, GroupDMUpdate(name="x"))
            with pytest.raises(ForbiddenException):
                await w.call(ChannelService, "leave_group_dm", me, dm)
            assert await members_of(w, dm) == {me.id, f1.id}

    run(scenario())


def test_any_member_renames_and_a_stranger_cannot(side_effects):
    async def scenario():
        async with world() as w:
            a, b, c, out = [await w.user(n) for n in ("a", "b", "c", "out")]
            group = await w.channel(ChannelType.GROUP_DM, a, b, c)
            with pytest.raises(NotFoundException):
                await w.call(ChannelService, "update_group_dm", out, group, GroupDMUpdate(name="mine"))
            channel = await w.call(ChannelService, "update_group_dm", c, group, GroupDMUpdate(name="  Trip  "))
            assert channel.name == "Trip"
            channel = await w.call(ChannelService, "update_group_dm", b, group, GroupDMUpdate(name="   "))
            assert channel.name is None

    run(scenario())


def test_the_owner_leaving_hands_the_room_to_the_longest_standing_member(side_effects):
    async def scenario():
        async with world() as w:
            a, b, c = [await w.user(n) for n in "abc"]
            group = await w.channel(ChannelType.GROUP_DM, a, b, c)
            await w.call(ChannelService, "leave_group_dm", a, group)
            assert await owner_of(w, group) == b.id
            assert await members_of(w, group) == {b.id, c.id}
            assert side_effects.removed_from_rooms == [([group], a.id)]

            # A non-owner leaving changes nothing about ownership
            await w.call(ChannelService, "leave_group_dm", c, group)
            assert await owner_of(w, group) == b.id

    run(scenario())


def test_the_last_one_out_deletes_the_channel_and_its_messages(side_effects):
    async def scenario():
        async with world() as w:
            a, b, c = [await w.user(n) for n in "abc"]
            group = await w.channel(ChannelType.GROUP_DM, a, b, c)
            async with w.session() as db:
                db.add(Message(content="hi", sender_id=a.id, channel_id=group))
                await db.commit()
            for person in (a, b, c):
                await w.call(ChannelService, "leave_group_dm", person, group)
            assert await w.scalar(select(Channel.id).where(Channel.id == group)) is None
            assert await w.scalars(select(Message.id)) == []

    run(scenario())


# --------------------------------------------------------------------------
# Guild channels
# --------------------------------------------------------------------------


async def a_guild(w):
    owner, admin, mem, out = [await w.user(n) for n in ("owner", "admin", "mem", "out")]
    guild_id = await w.guild(owner)
    await w.member(guild_id, admin, GuildMemberRole.ADMIN)
    await w.member(guild_id, mem)
    return guild_id, dict(owner=owner, admin=admin, mem=mem, out=out)


NEW = GuildChannelCreate(type=ChannelType.GUILD_TEXT, name="new")


def test_creating_a_guild_channel_is_for_admins(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            with pytest.raises(ForbiddenException):
                await w.call(ChannelService, "create_guild_channel", p["mem"], guild_id, NEW)
            with pytest.raises(NotFoundException):
                await w.call(ChannelService, "create_guild_channel", p["out"], guild_id, NEW)
            channel = await w.call(ChannelService, "create_guild_channel", p["admin"], guild_id, NEW)
            # Every member of the guild is in the new channel, and nobody else
            assert await members_of(w, channel.id) == {p["owner"].id, p["admin"].id, p["mem"].id}

    run(scenario())


def test_deleting_a_guild_channel_is_for_admins_and_never_a_dm(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            channel = await w.call(ChannelService, "create_guild_channel", p["admin"], guild_id, NEW)
            with pytest.raises(ForbiddenException):
                await w.call(ChannelService, "delete_guild_channel", p["mem"], str(channel.id))
            with pytest.raises(NotFoundException):
                await w.call(ChannelService, "delete_guild_channel", p["out"], str(channel.id))
            await w.call(ChannelService, "delete_guild_channel", p["admin"], str(channel.id))
            assert await w.scalar(select(Channel.id).where(Channel.id == channel.id)) is None
            assert side_effects.closed_rooms == [str(channel.id)]

            dm = await w.channel(ChannelType.DM, p["mem"], p["out"])
            with pytest.raises(ForbiddenException):
                await w.call(ChannelService, "delete_guild_channel", p["mem"], dm)

    run(scenario())
