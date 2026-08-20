import { useEffect } from "react";
import { FiX } from "react-icons/fi";
import { useGuildStore } from "./guildStore";
import { useUserStore } from "../shared/userStore";
import { useUiStore } from "../shared/uiStore";
import { GuildMemberRole } from "./types";
import Avatar from "../shared/Avatar";

/**
 * Guild members. A permanent third column from `xl` up; below that it is a
 * drawer opened from the channel header, because three columns do not fit on a
 * laptop, let alone a phone.
 */
export default function GuildMembersBar({ guildId }: { guildId: string }) {
  const { getMembers, fetchGuildMembers } = useGuildStore();
  const { getUser: getUserFromStore, fetchUsers } = useUserStore();
  const { membersOpen, setMembersOpen } = useUiStore();
  const members = getMembers(guildId);

  useEffect(() => {
    fetchGuildMembers(guildId);
  }, [guildId, fetchGuildMembers]);

  useEffect(() => {
    if (members.length > 0) fetchUsers(members.map((m) => m.user_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [members.length, fetchUsers]);

  const admins = members.filter((m) => m.role === GuildMemberRole.ADMIN);
  const rest = members.filter((m) => m.role !== GuildMemberRole.ADMIN);

  const group = (label: string, list: typeof members) =>
    list.length > 0 && (
      <div key={label}>
        <p className="px-2 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-widest text-ink-400">
          {label} ({list.length})
        </p>
        <ul className="space-y-0.5">
          {list.map((member) => (
            <li
              key={member.user_id}
              className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-white/[0.04]"
            >
              <Avatar
                name={getUserFromStore(member.user_id)?.username}
                seed={member.user_id}
                size="sm"
              />
              <span className="min-w-0 flex-1 truncate text-sm text-ink-200">
                {getUserFromStore(member.user_id)?.username ?? "…"}
              </span>
              {member.role === GuildMemberRole.ADMIN && (
                <span className="rounded-md bg-rain-400/15 px-1.5 py-0.5 text-[10px] font-medium text-rain-300">
                  admin
                </span>
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
          {group("Admins", admins)}
          {group("Members", rest)}
        </div>
      </aside>
    </>
  );
}
