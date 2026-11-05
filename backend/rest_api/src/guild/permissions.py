"""Who may do what in a guild. The one place that answers it.

Pure on purpose: no database and no request, so the whole policy is a table and
two comparisons that a unit test can walk exhaustively. The service looks up a
caller's `Standing` and asks here; nothing else compares against a role.

**Every role is the answer to a specific question.**

- A member can talk, and can invite. Invites were open to any member before
  roles did anything, and a guild is not a private club by default.
- A moderator answers "who deals with someone being disruptive when the owner
  is not around". That is removing people and their messages, and nothing that
  changes the guild.
- An admin answers "who else can run this place". Channels, the guild's name
  and icon, and other people's roles.
- The owner is **not a role**. It is `Guild.owner_id`, and it outranks
  everything. Only it can delete the guild, because that is the one action with
  no undo and every member's history behind it, or give the guild away. The
  creator also holds the
  `ADMIN` row, so that a guild whose owner account is deleted (`owner_id` goes
  null) still has someone who can run it.

**You act only on people below you.** Being outranked is what protects an admin
from another admin and the owner from everyone. It also means nobody acts on
themselves, so no route can be used to promote yourself.
"""

from dataclasses import dataclass
from enum import Enum

from libs.db import GuildMemberRole


class GuildPermission(Enum):
    INVITE = "invite"
    KICK = "kick"
    MANAGE_MESSAGES = "manage_messages"
    MANAGE_CHANNELS = "manage_channels"
    MANAGE_GUILD = "manage_guild"
    MANAGE_ROLES = "manage_roles"
    DELETE_GUILD = "delete_guild"
    TRANSFER_OWNERSHIP = "transfer_ownership"


# Written out rather than each role extending the last: this table is the
# policy, and it should read as one. `DELETE_GUILD` and `TRANSFER_OWNERSHIP` are
# deliberately in no row.
ROLE_PERMISSIONS: dict[GuildMemberRole, frozenset[GuildPermission]] = {
    GuildMemberRole.MEMBER: frozenset({GuildPermission.INVITE}),
    GuildMemberRole.MODERATOR: frozenset(
        {
            GuildPermission.INVITE,
            GuildPermission.KICK,
            GuildPermission.MANAGE_MESSAGES,
        }
    ),
    GuildMemberRole.ADMIN: frozenset(
        {
            GuildPermission.INVITE,
            GuildPermission.KICK,
            GuildPermission.MANAGE_MESSAGES,
            GuildPermission.MANAGE_CHANNELS,
            GuildPermission.MANAGE_GUILD,
            GuildPermission.MANAGE_ROLES,
        }
    ),
}

ROLE_RANK: dict[GuildMemberRole, int] = {
    GuildMemberRole.MEMBER: 0,
    GuildMemberRole.MODERATOR: 1,
    GuildMemberRole.ADMIN: 2,
}
OWNER_RANK = 3

# The sentence a refusal reads as. `errorText` shows `detail` to the person.
DENIED: dict[GuildPermission, str] = {
    GuildPermission.INVITE: "You cannot invite people to this guild",
    GuildPermission.KICK: "Only moderators and admins can remove members",
    GuildPermission.MANAGE_MESSAGES: "You can only delete your own messages",
    GuildPermission.MANAGE_CHANNELS: "Only guild admins can manage channels",
    GuildPermission.MANAGE_GUILD: "Only guild admins can change the guild",
    GuildPermission.MANAGE_ROLES: "Only guild admins can change roles",
    GuildPermission.DELETE_GUILD: "Only the owner can delete a guild",
    GuildPermission.TRANSFER_OWNERSHIP: "Only the owner can transfer a guild",
}


@dataclass(frozen=True)
class Standing:
    """Where one member stands in one guild."""

    role: GuildMemberRole
    is_owner: bool = False

    @property
    def rank(self) -> int:
        return OWNER_RANK if self.is_owner else ROLE_RANK[self.role]


def allows(standing: Standing, permission: GuildPermission) -> bool:
    if standing.is_owner:
        return True
    return permission in ROLE_PERMISSIONS[standing.role]


def outranks(actor: Standing, target: Standing) -> bool:
    """Strictly. Equals cannot act on each other, and nobody on themselves."""
    return actor.rank > target.rank


def can_assign(
    actor: Standing, target: Standing, new_role: GuildMemberRole
) -> bool:
    """May `actor` give `target` this role?

    An admin may make another admin, which grants nothing they do not hold, but
    cannot then undo it: only the owner outranks both.
    """
    return (
        allows(actor, GuildPermission.MANAGE_ROLES)
        and outranks(actor, target)
        and ROLE_RANK[new_role] <= actor.rank
    )
