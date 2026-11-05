import { useAuth } from "../auth/AuthContext";
import { useGuildStore } from "./guildStore";
import { GuildMemberRole, type Guild, type GuildMember } from "./types";

/**
 * Mirrors `rest_api/src/guild/permissions.py`, and only decides what to show:
 * the server checks every action regardless, so a wrong answer here costs a 403
 * and nothing more. Keep the two tables in step.
 */
export enum GuildPermission {
  INVITE = "invite",
  KICK = "kick",
  MANAGE_MESSAGES = "manage_messages",
  MANAGE_CHANNELS = "manage_channels",
  MANAGE_GUILD = "manage_guild",
  MANAGE_ROLES = "manage_roles",
  DELETE_GUILD = "delete_guild",
  TRANSFER_OWNERSHIP = "transfer_ownership",
}

const ROLE_PERMISSIONS: Record<GuildMemberRole, GuildPermission[]> = {
  [GuildMemberRole.MEMBER]: [GuildPermission.INVITE],
  [GuildMemberRole.MODERATOR]: [
    GuildPermission.INVITE,
    GuildPermission.KICK,
    GuildPermission.MANAGE_MESSAGES,
  ],
  [GuildMemberRole.ADMIN]: [
    GuildPermission.INVITE,
    GuildPermission.KICK,
    GuildPermission.MANAGE_MESSAGES,
    GuildPermission.MANAGE_CHANNELS,
    GuildPermission.MANAGE_GUILD,
    GuildPermission.MANAGE_ROLES,
  ],
};

const ROLE_RANK: Record<GuildMemberRole, number> = {
  [GuildMemberRole.MEMBER]: 0,
  [GuildMemberRole.MODERATOR]: 1,
  [GuildMemberRole.ADMIN]: 2,
};
const OWNER_RANK = 3;

/** `role` is undefined until the member list has loaded. */
export type Standing = { role?: GuildMemberRole; isOwner: boolean };

const rank = (standing: Standing) => {
  if (standing.isOwner) return OWNER_RANK;
  return standing.role ? ROLE_RANK[standing.role] : -1;
};

export const allows = (standing: Standing, permission: GuildPermission) =>
  standing.isOwner ||
  (!!standing.role && ROLE_PERMISSIONS[standing.role].includes(permission));

/** Strictly: equals cannot act on each other, and nobody on themselves. */
export const outranks = (actor: Standing, target: Standing) =>
  rank(actor) > rank(target);

/** The roles `actor` may hand out, lowest first. */
export const assignableRoles = (actor: Standing) =>
  [
    GuildMemberRole.MEMBER,
    GuildMemberRole.MODERATOR,
    GuildMemberRole.ADMIN,
  ].filter((role) => ROLE_RANK[role] <= rank(actor));

export const standingOf = (
  guild: Guild | undefined,
  member: GuildMember
): Standing => ({
  role: member.role,
  isOwner: guild?.owner_id === member.user_id,
});

/** The signed-in user's standing in a guild. */
export function useGuildStanding(guildId: string | undefined): Standing {
  const { getCurrentUser } = useAuth();
  const selfId = getCurrentUser()?.id;
  const isOwner = useGuildStore(
    (state) =>
      !!selfId &&
      state.guilds.find((guild) => guild.id === guildId)?.owner_id === selfId
  );
  const role = useGuildStore(
    (state) =>
      state.members[guildId ?? ""]?.find((member) => member.user_id === selfId)
        ?.role
  );
  return { role, isOwner };
}
