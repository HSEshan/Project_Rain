import { useEffect } from "react";
import { useGuildStore } from "./guildStore";
import { useUserStore } from "../shared/userStore";
import { GuildMemberRole } from "./types";
import { PiUserCircle } from "react-icons/pi";

export default function GuildMembersBar({ guildId }: { guildId: string }) {
  const { getMembers, fetchGuildMembers } = useGuildStore();
  const { getUser: getUserFromStore, fetchUsers } = useUserStore();
  const members = getMembers(guildId);

  useEffect(() => {
    fetchGuildMembers(guildId);
  }, [guildId, fetchGuildMembers]);

  useEffect(() => {
    if (members.length > 0) fetchUsers(members.map((m) => m.user_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [members.length, fetchUsers]);

  return (
    <div className="w-48 bg-gray-900 text-white flex flex-col px-3 py-4 gap-2 flex-shrink-0">
      <h2 className="text-xs uppercase tracking-wide text-gray-400">
        Members — {members.length}
      </h2>
      <div className="flex flex-col gap-1 overflow-y-auto">
        {members.map((member) => (
          <div
            key={member.user_id}
            className="flex items-center gap-2 text-sm px-1 py-1"
          >
            <PiUserCircle size={22} className="flex-shrink-0" />
            <span className="truncate">
              {getUserFromStore(member.user_id)?.username ?? "Loading..."}
            </span>
            {member.role === GuildMemberRole.ADMIN && (
              <span className="ml-auto text-[10px] text-blue-400">admin</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
