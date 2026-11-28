"""Invite links: who may make, see and revoke one, and when one stops working.

The code is the credential, so the interesting rules are the refusals: a dead
link answers exactly like one that never existed, and nothing that refuses
spends a use.
"""

from datetime import datetime, timedelta, timezone

import pytest
from libs.db import GuildInviteLink, GuildMember, GuildMemberRole
from sqlalchemy import select, update
from src.guild.invite_links import INVALID_LINK, MAX_LINKS_PER_GUILD, InviteLinkService
from src.guild.schemas import InviteLinkCreate
from src.utils.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from tests.service_db import run, side_effects, world  # noqa: F401


async def setup(w):
    owner, admin, mem, mem2, out = [
        await w.user(n) for n in ("owner", "admin", "mem", "mem2", "out")
    ]
    guild_id = await w.guild(owner)
    await w.member(guild_id, admin, GuildMemberRole.ADMIN)
    await w.member(guild_id, mem)
    await w.member(guild_id, mem2)
    return guild_id, dict(owner=owner, admin=admin, mem=mem, mem2=mem2, out=out)


async def uses(w, code):
    return await w.scalar(select(GuildInviteLink.uses).where(GuildInviteLink.code == code))


async def make(w, who, guild_id, **kwargs):
    return await w.call(
        InviteLinkService, "create_link", who, guild_id, InviteLinkCreate(**kwargs)
    )


def test_a_stranger_cannot_make_a_link(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            with pytest.raises(NotFoundException):
                await make(w, p["out"], guild_id)

    run(scenario())


def test_codes_are_long_and_distinct(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            codes = {(await make(w, p["mem"], guild_id)).code for _ in range(5)}
            assert len(codes) == 5
            assert all(len(code) >= 16 for code in codes)

    run(scenario())


def test_members_see_their_own_links_and_admins_see_all(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            mine = await make(w, p["mem"], guild_id)
            theirs = await make(w, p["mem2"], guild_id)

            seen = {l.code for l in await w.call(InviteLinkService, "list_links", p["mem"], guild_id)}
            assert seen == {mine.code}
            seen = {l.code for l in await w.call(InviteLinkService, "list_links", p["admin"], guild_id)}
            assert seen == {mine.code, theirs.code}
            with pytest.raises(NotFoundException):
                await w.call(InviteLinkService, "list_links", p["out"], guild_id)

    run(scenario())


def test_only_the_creator_or_an_admin_revokes(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            link = await make(w, p["mem"], guild_id)
            with pytest.raises(ForbiddenException):
                await w.call(InviteLinkService, "revoke_link", p["mem2"], guild_id, link.code)
            with pytest.raises(NotFoundException):
                await w.call(InviteLinkService, "revoke_link", p["out"], guild_id, link.code)
            await w.call(InviteLinkService, "revoke_link", p["admin"], guild_id, link.code)
            assert await uses(w, link.code) is None

            own = await make(w, p["mem2"], guild_id)
            await w.call(InviteLinkService, "revoke_link", p["mem2"], guild_id, own.code)
            assert await uses(w, own.code) is None

    run(scenario())


def test_a_code_from_another_guild_cannot_be_revoked_through_this_one(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            other_guild = await w.guild(p["out"], "Other")
            foreign = await make(w, p["out"], other_guild)
            # Admin here, nothing there
            with pytest.raises(NotFoundException):
                await w.call(InviteLinkService, "revoke_link", p["admin"], guild_id, foreign.code)
            assert await uses(w, foreign.code) == 0

    run(scenario())


def test_accepting_joins_and_counts_one_use(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            link = await make(w, p["mem"], guild_id, max_uses=2)
            result = await w.call(InviteLinkService, "accept", p["out"], link.code)
            assert result.already_member is False
            assert result.guild_id == guild_id
            assert await uses(w, link.code) == 1
            assert p["out"].id in side_effects.invalidated

    run(scenario())


def test_a_member_following_a_link_spends_nothing(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            link = await make(w, p["mem"], guild_id, max_uses=1)
            result = await w.call(InviteLinkService, "accept", p["mem2"], link.code)
            assert result.already_member is True
            assert await uses(w, link.code) == 0

    run(scenario())


def test_a_used_up_link_is_dead_and_says_so_like_a_missing_one(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            link = await make(w, p["mem"], guild_id, max_uses=1)
            late = await w.user("late")
            await w.call(InviteLinkService, "accept", p["out"], link.code)

            with pytest.raises(NotFoundException) as used_up:
                await w.call(InviteLinkService, "accept", late, link.code)
            with pytest.raises(NotFoundException) as missing:
                await w.call(InviteLinkService, "accept", late, "no-such-code")
            assert used_up.value.detail == missing.value.detail == INVALID_LINK
            assert await uses(w, link.code) == 1
            with pytest.raises(NotFoundException):
                await w.call(InviteLinkService, "preview", link.code)

    run(scenario())


def test_an_expired_link_is_dead(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            link = await make(w, p["mem"], guild_id, expires_in_hours=1)
            async with w.session() as db:
                await db.execute(
                    update(GuildInviteLink)
                    .where(GuildInviteLink.code == link.code)
                    .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
                )
                await db.commit()
            with pytest.raises(NotFoundException) as refused:
                await w.call(InviteLinkService, "accept", p["out"], link.code)
            assert refused.value.detail == INVALID_LINK
            with pytest.raises(NotFoundException):
                await w.call(InviteLinkService, "preview", link.code)
            assert await w.call(InviteLinkService, "list_links", p["mem"], guild_id) == []

    run(scenario())


def test_the_preview_says_only_what_the_guild_is(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            link = await make(w, p["mem"], guild_id)
            preview = await w.call(InviteLinkService, "preview", link.code)
            assert preview.member_count == 4
            assert set(preview.model_dump()) == {
                "guild_name",
                "guild_description",
                "icon_url",
                "member_count",
            }

    run(scenario())


def test_a_guild_holds_a_bounded_number_of_live_links(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            for _ in range(MAX_LINKS_PER_GUILD):
                await make(w, p["mem"], guild_id)
            with pytest.raises(BadRequestException):
                await make(w, p["mem2"], guild_id)

            # Dead links do not count, and making a new one clears them
            async with w.session() as db:
                await db.execute(
                    update(GuildInviteLink).values(max_uses=1, uses=1)
                )
                await db.commit()
            await make(w, p["mem2"], guild_id)
            assert len(await w.scalars(select(GuildInviteLink.code))) == 1

    run(scenario())


def test_a_link_from_a_member_who_left_stops_working(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, p = await setup(w)
            link = await make(w, p["mem"], guild_id)
            from src.guild.service import GuildService

            await w.call(GuildService, "leave_guild", p["mem"], guild_id)
            with pytest.raises(NotFoundException):
                await w.call(InviteLinkService, "accept", p["out"], link.code)
            assert await w.scalar(
                select(GuildMember.user_id).where(GuildMember.user_id == p["out"].id)
            ) is None

    run(scenario())
