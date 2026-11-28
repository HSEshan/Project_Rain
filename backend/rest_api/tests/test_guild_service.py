"""Who may invite, kick, ban, leave and hand over a guild, against a real database.

`test_guild_permissions.py` walks the pure policy table. This file is the other
half: that `GuildService` actually asks it, in the right order, with the right
target, and that the rows left behind match the rule (a kicked member is out of
every channel, a banned one cannot come back, a declined invite is gone).
"""

from datetime import datetime, timedelta, timezone

import pytest
from libs.db import (
    ChannelMember,
    GuildBan,
    GuildInvite,
    GuildInviteLink,
    GuildMember,
    GuildMemberRole,
)
from sqlalchemy import select, update
from src.guild.schemas import GuildUpdate, InviteLinkCreate
from src.utils.exceptions import (
    AlreadyExistsException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from tests.service_db import run, side_effects, world  # noqa: F401

from src.guild.invite_links import InviteLinkService  # noqa: E402
from src.guild.service import GuildService  # noqa: E402

ADMIN, MODERATOR, MEMBER = (
    GuildMemberRole.ADMIN,
    GuildMemberRole.MODERATOR,
    GuildMemberRole.MEMBER,
)


async def a_guild(w):
    """Owner, an admin, a moderator, a member, and a stranger."""
    people = {name: await w.user(name) for name in ("owner", "admin", "mod", "mem", "out")}
    guild_id = await w.guild(people["owner"])
    await w.member(guild_id, people["admin"], ADMIN)
    await w.member(guild_id, people["mod"], MODERATOR)
    await w.member(guild_id, people["mem"], MEMBER)
    return guild_id, people


async def is_member(w, guild_id, user) -> bool:
    return (
        await w.scalar(
            select(GuildMember.user_id).where(
                GuildMember.guild_id == guild_id, GuildMember.user_id == user.id
            )
        )
        is not None
    )


async def channel_memberships(w, guild_id, user) -> int:
    channels = [c.id for c in await w.guild_channels(guild_id)]
    rows = await w.scalars(
        select(ChannelMember.id).where(
            ChannelMember.user_id == user.id, ChannelMember.channel_id.in_(channels)
        )
    )
    return len(rows)


# --------------------------------------------------------------------------
# Personal invites
# --------------------------------------------------------------------------


def test_a_stranger_cannot_invite_and_is_told_404_not_403(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            target = await w.user("target")
            with pytest.raises(NotFoundException):
                await w.call(
                    GuildService, "create_guild_invite", p["out"], guild_id, target.id
                )

    run(scenario())


def test_any_member_can_invite_and_the_recipient_is_told(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            target = await w.user("target")
            invite = await w.call(
                GuildService, "create_guild_invite", p["mem"], guild_id, target.id
            )
            assert str(invite.inviter_id) == p["mem"].id
            assert target.id in side_effects.recipients()

    run(scenario())


def test_inviting_by_username(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            target = await w.user("target")
            invite = await w.call(
                GuildService,
                "create_guild_invite",
                p["mem"],
                guild_id,
                username="target",
            )
            assert str(invite.user_id) == target.id
            with pytest.raises(NotFoundException):
                await w.call(
                    GuildService,
                    "create_guild_invite",
                    p["mem"],
                    guild_id,
                    username="nobody-by-this-name",
                )

    run(scenario())


def test_cannot_invite_a_member_or_invite_twice(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            with pytest.raises(AlreadyExistsException):
                await w.call(
                    GuildService, "create_guild_invite", p["mem"], guild_id, p["mod"].id
                )
            target = await w.user("target")
            await w.call(GuildService, "create_guild_invite", p["mem"], guild_id, target.id)
            with pytest.raises(AlreadyExistsException):
                await w.call(
                    GuildService, "create_guild_invite", p["admin"], guild_id, target.id
                )

    run(scenario())


def test_only_the_recipient_can_accept_or_decline(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            target = await w.user("target")
            invite = await w.call(
                GuildService, "create_guild_invite", p["mem"], guild_id, target.id
            )
            for someone in (p["out"], p["owner"]):
                with pytest.raises(ForbiddenException):
                    await w.call(
                        GuildService, "accept_guild_invite", someone, invite.invite_id
                    )
                with pytest.raises(ForbiddenException):
                    await w.call(
                        GuildService, "decline_guild_invite", someone, invite.invite_id
                    )
            assert not await is_member(w, guild_id, p["out"])

    run(scenario())


def test_accepting_joins_every_channel_and_spends_the_invite(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            target = await w.user("target")
            invite = await w.call(
                GuildService, "create_guild_invite", p["mem"], guild_id, target.id
            )
            await w.call(GuildService, "accept_guild_invite", target, invite.invite_id)

            assert await is_member(w, guild_id, target)
            assert await channel_memberships(w, guild_id, target) == 2
            assert await w.scalar(
                select(GuildInvite.invite_id).where(GuildInvite.user_id == target.id)
            ) is None
            assert target.id in side_effects.invalidated
            with pytest.raises(NotFoundException):
                await w.call(
                    GuildService, "accept_guild_invite", target, invite.invite_id
                )

    run(scenario())


def test_an_expired_invite_cannot_be_accepted(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            target = await w.user("target")
            invite = await w.call(
                GuildService, "create_guild_invite", p["mem"], guild_id, target.id
            )
            async with w.session() as db:
                await db.execute(
                    update(GuildInvite)
                    .where(GuildInvite.user_id == target.id)
                    .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
                )
                await db.commit()
            with pytest.raises(NotFoundException):
                await w.call(GuildService, "accept_guild_invite", target, invite.invite_id)
            assert not await is_member(w, guild_id, target)
            # Expired invites are hidden from the recipient's list
            assert await w.call(GuildService, "get_user_guild_invites", target) == []

    run(scenario())


def test_declining_deletes_the_invite(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            target = await w.user("target")
            invite = await w.call(
                GuildService, "create_guild_invite", p["mem"], guild_id, target.id
            )
            assert len(await w.call(GuildService, "get_user_guild_invites", target)) == 1
            await w.call(GuildService, "decline_guild_invite", target, invite.invite_id)
            assert await w.call(GuildService, "get_user_guild_invites", target) == []
            assert not await is_member(w, guild_id, target)

    run(scenario())


# --------------------------------------------------------------------------
# Removing people
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "actor, target, allowed",
    [
        ("mem", "mod", False),  # no KICK at all
        ("mem", "out", False),  # not a member, either way
        ("mod", "mem", True),
        ("mod", "mod2", False),  # equals
        ("mod", "admin", False),
        ("admin", "mod", True),
        ("admin", "admin2", False),
        ("admin", "owner", False),  # the owner's row says ADMIN too
        ("owner", "admin", True),
        ("owner", "owner", False),  # nobody removes themselves through this route
        ("mod", "mod", False),
    ],
)
def test_kick_follows_rank(side_effects, actor, target, allowed):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            p["mod2"] = await w.user("mod2")
            p["admin2"] = await w.user("admin2")
            await w.member(guild_id, p["mod2"], MODERATOR)
            await w.member(guild_id, p["admin2"], ADMIN)

            call = w.call(
                GuildService, "remove_guild_member", p[actor], guild_id, p[target].id
            )
            if allowed:
                await call
                assert not await is_member(w, guild_id, p[target])
            else:
                with pytest.raises((ForbiddenException, NotFoundException)):
                    await call
                if target != "out":
                    assert await is_member(w, guild_id, p[target])

    run(scenario())


def test_kick_without_permission_is_403_and_non_member_is_404(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            with pytest.raises(ForbiddenException):
                await w.call(
                    GuildService, "remove_guild_member", p["mem"], guild_id, p["mod"].id
                )
            with pytest.raises(NotFoundException):
                await w.call(
                    GuildService, "remove_guild_member", p["out"], guild_id, p["mem"].id
                )
            # A target who is not in the guild
            with pytest.raises(NotFoundException):
                await w.call(
                    GuildService, "remove_guild_member", p["admin"], guild_id, p["out"].id
                )

    run(scenario())


def test_a_kick_leaves_every_channel_ends_their_links_and_their_calls(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            link = await w.call(
                InviteLinkService, "create_link", p["mem"], guild_id, InviteLinkCreate()
            )
            await w.call(GuildService, "remove_guild_member", p["mod"], guild_id, p["mem"].id)

            assert await channel_memberships(w, guild_id, p["mem"]) == 0
            # A kick the kicked person can undo with a URL they kept is no kick
            assert await w.scalar(
                select(GuildInviteLink.code).where(GuildInviteLink.code == link.code)
            ) is None
            assert p["mem"].id in side_effects.invalidated
            voice = [
                str(c.id) for c in await w.guild_channels(guild_id) if c.type.value == "guild_voice"
            ]
            assert side_effects.removed_from_rooms == [(voice, p["mem"].id)]

    run(scenario())


# --------------------------------------------------------------------------
# Bans
# --------------------------------------------------------------------------


def test_a_ban_keeps_them_out_of_every_door(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            link = await w.call(
                InviteLinkService, "create_link", p["owner"], guild_id, InviteLinkCreate(max_uses=5)
            )
            await w.call(
                GuildService, "remove_guild_member", p["mod"], guild_id, p["mem"].id, ban=True
            )
            assert not await is_member(w, guild_id, p["mem"])

            # Personal invite: refused at creation
            with pytest.raises(ForbiddenException):
                await w.call(
                    GuildService, "create_guild_invite", p["admin"], guild_id, p["mem"].id
                )
            # Invite link: refused at accept, and the use is not spent
            with pytest.raises(ForbiddenException):
                await w.call(InviteLinkService, "accept", p["mem"], link.code)
            uses = await w.scalar(
                select(GuildInviteLink.uses).where(GuildInviteLink.code == link.code)
            )
            assert uses == 0
            assert not await is_member(w, guild_id, p["mem"])

    run(scenario())


def test_a_ban_removes_an_open_invite_so_it_cannot_be_accepted_later(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            # An invite row for someone who is also a member cannot exist through
            # the service, so put one in directly: the ban must clear it.
            async with w.session() as db:
                db.add(GuildInvite(guild_id=guild_id, user_id=p["mem"].id))
                await db.commit()
            await w.call(
                GuildService, "remove_guild_member", p["mod"], guild_id, p["mem"].id, ban=True
            )
            assert await w.scalar(
                select(GuildInvite.invite_id).where(GuildInvite.user_id == p["mem"].id)
            ) is None

    run(scenario())


def test_ban_list_and_unban_need_kick(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            await w.call(
                GuildService, "remove_guild_member", p["mod"], guild_id, p["mem"].id, ban=True
            )
            # The banned person is no longer a member, so not even a 403
            with pytest.raises(NotFoundException):
                await w.call(GuildService, "list_bans", p["mem"], guild_id)
            other = await w.user("other")
            await w.member(guild_id, other, MEMBER)
            with pytest.raises(ForbiddenException):
                await w.call(GuildService, "list_bans", other, guild_id)
            with pytest.raises(ForbiddenException):
                await w.call(GuildService, "remove_ban", other, guild_id, p["mem"].id)
            with pytest.raises(NotFoundException):
                await w.call(GuildService, "list_bans", p["out"], guild_id)

            bans = await w.call(GuildService, "list_bans", p["mod"], guild_id)
            assert [b.user_id for b in bans] == [p["mem"].id]

    run(scenario())


def test_unban_lets_them_back_by_invite_but_does_not_bring_them_back(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            await w.call(
                GuildService, "remove_guild_member", p["mod"], guild_id, p["mem"].id, ban=True
            )
            await w.call(GuildService, "remove_ban", p["mod"], guild_id, p["mem"].id)
            assert not await is_member(w, guild_id, p["mem"])
            assert await w.scalar(select(GuildBan.user_id)) is None

            with pytest.raises(NotFoundException):
                await w.call(GuildService, "remove_ban", p["mod"], guild_id, p["mem"].id)

            link = await w.call(
                InviteLinkService, "create_link", p["owner"], guild_id, InviteLinkCreate()
            )
            await w.call(InviteLinkService, "accept", p["mem"], link.code)
            assert await is_member(w, guild_id, p["mem"])

    run(scenario())


# --------------------------------------------------------------------------
# Leaving, transfer, roles, settings, deletion
# --------------------------------------------------------------------------


def test_the_owner_cannot_leave_and_a_stranger_gets_404(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            with pytest.raises(ForbiddenException):
                await w.call(GuildService, "leave_guild", p["owner"], guild_id)
            with pytest.raises(NotFoundException):
                await w.call(GuildService, "leave_guild", p["out"], guild_id)
            assert await is_member(w, guild_id, p["owner"])

    run(scenario())


def test_leaving_drops_channels_and_links(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            await w.call(
                InviteLinkService, "create_link", p["admin"], guild_id, InviteLinkCreate()
            )
            await w.call(GuildService, "leave_guild", p["admin"], guild_id)
            assert not await is_member(w, guild_id, p["admin"])
            assert await channel_memberships(w, guild_id, p["admin"]) == 0
            assert await w.scalars(select(GuildInviteLink.code)) == []

    run(scenario())


def test_only_the_owner_can_transfer_and_only_to_a_member(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            with pytest.raises(ForbiddenException):
                await w.call(
                    GuildService, "transfer_ownership", p["admin"], guild_id, p["mem"].id
                )
            with pytest.raises(NotFoundException):
                await w.call(
                    GuildService, "transfer_ownership", p["owner"], guild_id, p["out"].id
                )
            with pytest.raises(BadRequestException):
                await w.call(
                    GuildService, "transfer_ownership", p["owner"], guild_id, p["owner"].id
                )

    run(scenario())


def test_after_a_transfer_the_old_owner_is_an_outranked_admin(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            guild = await w.call(
                GuildService, "transfer_ownership", p["owner"], guild_id, p["mem"].id
            )
            assert str(guild.owner_id) == p["mem"].id
            role = await w.scalar(
                select(GuildMember.role).where(
                    GuildMember.guild_id == guild_id, GuildMember.user_id == p["mem"].id
                )
            )
            assert role == ADMIN

            # The new owner can now remove the old one; the old one cannot act
            # on the new one, and can now leave.
            with pytest.raises(ForbiddenException):
                await w.call(
                    GuildService, "remove_guild_member", p["owner"], guild_id, p["mem"].id
                )
            with pytest.raises(ForbiddenException):
                await w.call(GuildService, "leave_guild", p["mem"], guild_id)
            await w.call(GuildService, "leave_guild", p["owner"], guild_id)

    run(scenario())


@pytest.mark.parametrize(
    "actor, target, new_role, allowed",
    [
        ("mod", "mem", MODERATOR, False),  # moderators manage no roles
        ("admin", "mem", ADMIN, True),
        ("admin", "mem", MODERATOR, True),
        ("admin", "mod", MEMBER, True),
        ("admin", "admin2", MEMBER, False),
        ("admin", "owner", MEMBER, False),
        ("admin", "admin", MEMBER, False),
        ("owner", "admin", MEMBER, True),
        ("mem", "mem", ADMIN, False),  # no self-promotion
    ],
)
def test_role_changes_follow_rank(side_effects, actor, target, new_role, allowed):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            p["admin2"] = await w.user("admin2")
            await w.member(guild_id, p["admin2"], ADMIN)
            call = w.call(
                GuildService, "update_member_role", p[actor], guild_id, p[target].id, new_role
            )
            before = await w.scalar(
                select(GuildMember.role).where(
                    GuildMember.guild_id == guild_id, GuildMember.user_id == p[target].id
                )
            )
            if allowed:
                await call
            else:
                with pytest.raises(ForbiddenException):
                    await call
            after = await w.scalar(
                select(GuildMember.role).where(
                    GuildMember.guild_id == guild_id, GuildMember.user_id == p[target].id
                )
            )
            assert after == (new_role if allowed else before)

    run(scenario())


def test_editing_the_guild_is_for_admins(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            for who in ("mem", "mod"):
                with pytest.raises(ForbiddenException):
                    await w.call(
                        GuildService, "update_guild", p[who], guild_id, GuildUpdate(name="x")
                    )
            with pytest.raises(NotFoundException):
                await w.call(
                    GuildService, "update_guild", p["out"], guild_id, GuildUpdate(name="x")
                )
            guild = await w.call(
                GuildService, "update_guild", p["admin"], guild_id, GuildUpdate(name="Renamed")
            )
            assert guild.name == "Renamed"
            # Only the fields named in the body are applied
            assert guild.description == "d"

    run(scenario())


def test_only_the_owner_deletes_the_guild_and_it_takes_its_channels(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            with pytest.raises(ForbiddenException):
                await w.call(GuildService, "delete_guild", p["admin"], guild_id)
            channels = [str(c.id) for c in await w.guild_channels(guild_id)]
            await w.call(GuildService, "delete_guild", p["owner"], guild_id)
            assert await w.guild_channels(guild_id) == []
            assert await w.scalars(select(GuildMember.user_id)) == []
            # Everyone who was in it is told, and the voice room is closed
            assert {p[n].id for n in ("owner", "admin", "mod", "mem")} <= side_effects.recipients()
            assert set(side_effects.closed_rooms) < set(channels)
            assert len(side_effects.closed_rooms) == 1

    run(scenario())


def test_reading_a_guild_needs_membership(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await a_guild(w)
            with pytest.raises(NotFoundException):
                await w.call(GuildService, "get_guild_for_user", p["out"], guild_id)
            guild = await w.call(GuildService, "get_guild_for_user", p["mem"], guild_id)
            assert str(guild.id) == guild_id

    run(scenario())
