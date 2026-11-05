"""The guild permission policy, walked exhaustively.

No database and no server: `src/guild/permissions.py` is pure so that this file
can check every role against every permission rather than the handful of pairs
an end-to-end test has the patience for.
"""

import pytest
from libs.db import GuildMemberRole
from src.guild.permissions import (
    DENIED,
    ROLE_PERMISSIONS,
    ROLE_RANK,
    GuildPermission,
    Standing,
    allows,
    can_assign,
    outranks,
)

MEMBER = Standing(GuildMemberRole.MEMBER)
MODERATOR = Standing(GuildMemberRole.MODERATOR)
ADMIN = Standing(GuildMemberRole.ADMIN)
# The creator's row says ADMIN. What makes them the owner is the column.
OWNER = Standing(GuildMemberRole.ADMIN, is_owner=True)

P = GuildPermission

EXPECTED = {
    MEMBER: {P.INVITE},
    MODERATOR: {P.INVITE, P.KICK, P.MANAGE_MESSAGES},
    ADMIN: {
        P.INVITE,
        P.KICK,
        P.MANAGE_MESSAGES,
        P.MANAGE_CHANNELS,
        P.MANAGE_GUILD,
        P.MANAGE_ROLES,
    },
    OWNER: set(GuildPermission),
}


@pytest.mark.parametrize("standing", EXPECTED, ids=lambda s: f"{s.role.value}-{s.is_owner}")
@pytest.mark.parametrize("permission", GuildPermission, ids=lambda p: p.value)
def test_every_role_against_every_permission(standing, permission):
    assert allows(standing, permission) is (permission in EXPECTED[standing])


def test_every_role_has_a_row_and_a_rank():
    # A role added to the enum and forgotten here would raise KeyError on the
    # first request from anyone holding it.
    assert set(ROLE_PERMISSIONS) == set(GuildMemberRole)
    assert set(ROLE_RANK) == set(GuildMemberRole)


def test_every_permission_has_a_refusal_sentence():
    assert set(DENIED) == set(GuildPermission)


def test_what_only_the_owner_can_do_is_in_no_role():
    for row in ROLE_PERMISSIONS.values():
        assert P.DELETE_GUILD not in row
        assert P.TRANSFER_OWNERSHIP not in row


def test_rank_is_strict_in_order():
    ladder = [MEMBER, MODERATOR, ADMIN, OWNER]
    for low, high in zip(ladder, ladder[1:]):
        assert outranks(high, low)
        assert not outranks(low, high)


@pytest.mark.parametrize("standing", [MEMBER, MODERATOR, ADMIN, OWNER])
def test_nobody_outranks_their_equal_or_themselves(standing):
    assert not outranks(standing, standing)


def test_the_owner_cannot_be_outranked_by_an_admin_row():
    # The trap in "the owner is not a role": two ADMIN rows, and only the column
    # tells them apart.
    assert OWNER.role == ADMIN.role
    assert not outranks(ADMIN, OWNER)
    assert outranks(OWNER, ADMIN)


@pytest.mark.parametrize("new_role", GuildMemberRole)
def test_nobody_can_assign_a_role_to_themselves(new_role):
    for standing in (MEMBER, MODERATOR, ADMIN, OWNER):
        assert not can_assign(standing, standing, new_role)


@pytest.mark.parametrize("new_role", GuildMemberRole)
def test_a_moderator_cannot_assign_anything(new_role):
    assert not can_assign(MODERATOR, MEMBER, new_role)


def test_an_admin_can_promote_a_member_as_far_as_admin():
    for new_role in GuildMemberRole:
        assert can_assign(ADMIN, MEMBER, new_role)


def test_an_admin_cannot_demote_another_admin_or_the_owner():
    assert not can_assign(ADMIN, ADMIN, GuildMemberRole.MEMBER)
    assert not can_assign(ADMIN, OWNER, GuildMemberRole.MEMBER)


def test_the_owner_can_demote_an_admin():
    assert can_assign(OWNER, ADMIN, GuildMemberRole.MEMBER)
