import { Link, useMatch } from "react-router-dom";
import { FiPlus, FiUserPlus, FiUsers } from "react-icons/fi";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import { useUiStore } from "../shared/uiStore";
import { useFriendStore } from "../friends/friendStore";
import { ChannelType } from "../shared/types";
import { useVoiceStore } from "../voice/voiceStore";
import Avatar from "../shared/Avatar";
import Badge from "../shared/Badge";
import SidePanel from "../shared/SidePanel";

export function MessageSidebar() {
  const { getDMChannels, getParticipants } = useChannelStore();
  const { setIsModalOpen, friendRequests } = useFriendStore();
  const { getUser: getUserFromStore } = useUserStore();
  const { setGroupCreateOpen } = useUiStore();
  const rosters = useVoiceStore((state) => state.rosters);
  // dmId belongs to a child route, so it is read from the URL directly
  const dmId = useMatch("/dm/:dmId")?.params.dmId;
  const onFriends = !!useMatch("/dm");
  const channels = getDMChannels();

  const participantNames = (channelId: string) =>
    getParticipants(channelId)
      .map((participant) => getUserFromStore(participant)?.username)
      .filter(Boolean)
      .join(", ");

  return (
    <SidePanel label="Direct messages">
      <div className="flex h-14 shrink-0 items-center px-4">
        <h2 className="text-[15px] font-semibold text-white">Messages</h2>
      </div>

      <div className="px-3 pb-3">
        <Link
          to="/dm"
          className={`flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm transition-colors ${
            onFriends
              ? "bg-white/[0.07] text-white"
              : "text-ink-300 hover:bg-white/[0.04] hover:text-white"
          }`}
        >
          <FiUsers size={16} className="shrink-0" />
          <span className="flex-1">Friends</span>
          <Badge count={friendRequests.length} />
        </Link>
      </div>

      <div className="flex items-center justify-between px-4 pb-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-ink-400">
          Direct messages
        </span>
        <span className="flex items-center gap-0.5">
          <button
            onClick={() => setGroupCreateOpen(true)}
            aria-label="New group"
            title="New group"
            className="rounded-md p-1 text-ink-400 transition-colors hover:bg-white/5 hover:text-white"
          >
            <FiUsers size={14} />
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            aria-label="Add friend"
            title="Add friend"
            className="rounded-md p-1 text-ink-400 transition-colors hover:bg-white/5 hover:text-white"
          >
            <FiPlus size={14} />
          </button>
        </span>
      </div>

      <div className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
        {channels.length === 0 ? (
          <p className="px-1 py-3 text-xs leading-relaxed text-ink-400">
            No conversations yet. Add a friend and a DM appears here the moment
            they accept.
          </p>
        ) : (
          channels.map((channel) => {
            const isGroup = channel.type === ChannelType.GROUP_DM;
            const members = participantNames(channel.id);
            const name =
              (isGroup ? channel.name || members : members) || "Loading…";
            // Someone is in a call here. The roster is filled by the same
            // VOICE_STATE events the call bar uses, so this needs no extra
            // request: it is the sidebar's version of a ringing phone.
            const inCall = (rosters[channel.id] ?? []).length > 0;

            return (
              <Link
                key={channel.id}
                to={`/dm/${channel.id}`}
                className={`flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm transition-colors ${
                  dmId === channel.id
                    ? "bg-white/[0.07] text-white"
                    : "text-ink-300 hover:bg-white/[0.04] hover:text-white"
                }`}
              >
                {isGroup ? (
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/[0.07] text-ink-200">
                    <FiUsers size={14} />
                  </span>
                ) : (
                  <Avatar name={name} seed={channel.id} size="sm" />
                )}
                <span className="min-w-0 flex-1 truncate">{name}</span>
                {inCall && (
                  <span
                    title="Call in progress"
                    aria-label="Call in progress"
                    className="h-2 w-2 shrink-0 rounded-full bg-emerald-400"
                  />
                )}
              </Link>
            );
          })
        )}
      </div>

      <div className="px-3 pb-4">
        <button
          onClick={() => setGroupCreateOpen(true)}
          className="flex w-full items-center gap-2 rounded-xl border border-dashed border-white/[0.09] px-3 py-2 text-xs text-ink-400 transition-colors hover:border-white/20 hover:text-white"
        >
          <FiUserPlus size={14} />
          New group
        </button>
      </div>
    </SidePanel>
  );
}
