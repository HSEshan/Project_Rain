import { useEffect, useState } from "react";
import { FiMoreVertical, FiX } from "react-icons/fi";
import { useGuildStore } from "./guildStore";
import { useUserStore } from "../shared/userStore";
import { useUiStore } from "../shared/uiStore";
import { GuildMemberRole, type GuildMember } from "./types";
import {
  GuildPermission,
  allows,
  outranks,
  standingOf,
  useGuildStanding,
} from "./permissions";
import GuildMemberModal from "./GuildMemberModal";
import Avatar from "../shared/Avatar";
import ProfileTrigger from "../profile/ProfileTrigger";

function RoleBadge({ label, accent }: { label: string; accent?: boolean }) {
  return (
    <span
      className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
        accent ? "bg-rain-400/15 text-rain-300" : "bg-white/[0.07] text-ink-300"
      }`}
    >
      {label}
    </span>
  );
}

/**
 * Guild members. A permanent third column from `xl` up; below that it is a
 * drawer opened from the channel header, because three columns do not fit on a
 * laptop, let alone a phone.
 */
export default function GuildMembersBar({ guildId }: { guildId: string }) {
  const { getMembers, getGuild } = useGuildStore();
  const { getUser: getUserFromStore, fetchUsers } = useUserStore();
  const { membersOpen, setMembersOpen } = useUiStore();
  const members = getMembers(guildId);
  const guild = getGuild(guildId);
  const standing = useGuildStanding(guildId);
  const canManageSomeone =
    allows(standing, GuildPermission.KICK) ||
    allows(standing, GuildPermission.MANAGE_ROLES);
  const [managingId, setManagingId] = useState<string | null>(null);
  // Looked up rather than held, so the modal shows the row as it is now
  const managing = members.find((m) => m.user_id === managingId) ?? null;

  useEffect(() => {
    if (members.length > 0) fetchUsers(members.map((m) => m.user_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [members.length, fetchUsers]);

  // The owner holds an admin row, so the column has to be asked first
  const isOwner = (m: GuildMember) => guild?.owner_id === m.user_id;
  const owners = members.filter(isOwner);
  const others = members.filter((m) => !isOwner(m));
  const admins = others.filter((m) => m.role === GuildMemberRole.ADMIN);
  const moderators = others.filter((m) => m.role === GuildMemberRole.MODERATOR);
  const rest = others.filter((m) => m.role === GuildMemberRole.MEMBER);

  const group = (label: string, list: typeof members) =>
    list.length > 0 && (
      <div key={label}>
        <p className="px-2 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-widest text-ink-400">
          {label} ({list.length})
        </p>
        <ul className="space-y-0.5">
          {list.map((member) => (
            <li key={member.user_id} className="flex items-center">
              <ProfileTrigger
                userId={member.user_id}
                className="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.04]"
              >
                <Avatar
                  name={getUserFromStore(member.user_id)?.username}
                  seed={member.user_id}
                  size="sm"
                />
                <span className="min-w-0 flex-1 truncate text-sm text-ink-200">
                  {getUserFromStore(member.user_id)?.username ?? "…"}
                </span>
                {isOwner(member) ? (
                  <RoleBadge label="owner" accent />
                ) : member.role === GuildMemberRole.ADMIN ? (
                  <RoleBadge label="admin" accent />
                ) : member.role === GuildMemberRole.MODERATOR ? (
                  <RoleBadge label="mod" />
                ) : null}
              </ProfileTrigger>
              {canManageSomeone &&
                outranks(standing, standingOf(guild, member)) && (
                  <button
                    onClick={() => setManagingId(member.user_id)}
                    aria-label={`Manage ${
                      getUserFromStore(member.user_id)?.username ?? "member"
                    }`}
                    className="shrink-0 rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-white/5 hover:text-white"
                  >
                    <FiMoreVertical size={14} />
                  </button>
                )}
            </li>
          ))}
        </ul>
      </div>
    );

  return (
    <>
      {membersOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink-950/70 backdrop-blur-sm animate-fade-in xl:hidden"
          onClick={() => setMembersOpen(false)}
          role="presentation"
        />
      )}

      <aside
        aria-label="Members"
        className={`fixed inset-y-0 right-0 z-40 flex w-64 shrink-0 flex-col border-l border-white/[0.06] bg-ink-900 px-2 pb-4 transition-transform duration-300 ease-out xl:static xl:z-auto xl:translate-x-0 xl:bg-ink-900/40 ${
          membersOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex h-14 shrink-0 items-center justify-between px-2">
          <span className="text-sm font-semibold text-white">Members</span>
          <button
            onClick={() => setMembersOpen(false)}
            aria-label="Close members"
            className="rounded-lg p-2 text-ink-400 hover:bg-white/5 hover:text-white xl:hidden"
          >
            <FiX size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {group("Owner", owners)}
          {group("Admins", admins)}
          {group("Moderators", moderators)}
          {group("Members", rest)}
        </div>
      </aside>

      {/* Outside the aside: it is transformed, which would make a `fixed`
          modal position against the drawer instead of the viewport. */}
      <GuildMemberModal
        guildId={guildId}
        member={managing}
        onClose={() => setManagingId(null)}
      />
    </>
  );
}
