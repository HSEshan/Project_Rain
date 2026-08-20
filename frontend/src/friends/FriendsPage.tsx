import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FiMessageCircle, FiUserPlus, FiUsers } from "react-icons/fi";
import { useFriendStore } from "./friendStore";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import FriendRequestList from "./FriendRequestList";
import Avatar from "../shared/Avatar";
import Badge from "../shared/Badge";
import { Button } from "../shared/Button";
import EmptyState from "../shared/EmptyState";
import ViewHeader from "../shared/ViewHeader";

type Tab = "all" | "incoming" | "sent";

/** Landing panel for /dm — friends, incoming requests and outgoing requests. */
export default function FriendsPage() {
  const { friends, outgoingRequests, friendRequests, setIsModalOpen } =
    useFriendStore();
  const { getDMChannelWithUser } = useChannelStore();
  const { getUser: getUserFromStore } = useUserStore();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("all");

  const openDM = (userId: string) => {
    const channel = getDMChannelWithUser(userId);
    if (channel) navigate(`/dm/${channel.id}`);
  };

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: "all", label: "All", count: friends.length },
    { id: "incoming", label: "Incoming", count: friendRequests.length },
    { id: "sent", label: "Sent", count: outgoingRequests.length },
  ];

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-ink-950">
      <ViewHeader
        icon={<FiUsers size={16} />}
        title="Friends"
        actions={
          <Button
            size="sm"
            variant="primary"
            icon={<FiUserPlus size={14} />}
            onClick={() => setIsModalOpen(true)}
          >
            <span className="hidden sm:inline">Add friend</span>
          </Button>
        }
      />

      <div className="flex shrink-0 gap-1 border-b border-white/[0.06] px-3 sm:px-6">
        {tabs.map((item) => (
          <button
            key={item.id}
            onClick={() => setTab(item.id)}
            className={`relative flex items-center gap-2 px-3 py-3 text-sm transition-colors ${
              tab === item.id
                ? "text-white"
                : "text-ink-400 hover:text-ink-200"
            }`}
          >
            {item.label}
            {item.id === "incoming" ? (
              <Badge count={item.count} />
            ) : (
              <span className="text-xs text-ink-500">{item.count}</span>
            )}
            {tab === item.id && (
              <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-rain-400" />
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
          {tab === "all" &&
            (friends.length === 0 ? (
              <EmptyState
                icon={<FiUsers size={22} />}
                title="No friends yet"
                hint="Add someone by their username. Once they accept, a direct message channel opens for both of you."
                action={
                  <Button
                    variant="primary"
                    icon={<FiUserPlus size={14} />}
                    onClick={() => setIsModalOpen(true)}
                  >
                    Add a friend
                  </Button>
                }
              />
            ) : (
              <ul className="space-y-1.5">
                {friends.map((friend) => {
                  const channel = getDMChannelWithUser(friend.id);
                  return (
                    <li
                      key={friend.id}
                      className="group flex items-center gap-3 rounded-2xl border border-white/[0.05] bg-white/[0.02] px-4 py-3 transition-colors hover:border-white/10 hover:bg-white/[0.04]"
                    >
                      <Avatar name={friend.username} seed={friend.id} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-ink-100">
                          {friend.username}
                        </span>
                        <span className="text-xs text-ink-500">Friend</span>
                      </span>
                      <Button
                        size="sm"
                        icon={<FiMessageCircle size={14} />}
                        onClick={() => openDM(friend.id)}
                        disabled={!channel}
                        title={channel ? "Open DM" : "DM channel not ready yet"}
                      >
                        Message
                      </Button>
                    </li>
                  );
                })}
              </ul>
            ))}

          {tab === "incoming" && <FriendRequestList />}

          {tab === "sent" &&
            (outgoingRequests.length === 0 ? (
              <EmptyState
                icon={<FiUserPlus size={22} />}
                title="Nothing pending"
                hint="Requests you send appear here until they are accepted."
              />
            ) : (
              <ul className="space-y-1.5">
                {outgoingRequests.map((request) => (
                  <li
                    key={request.id}
                    className="flex items-center gap-3 rounded-2xl border border-white/[0.05] bg-white/[0.02] px-4 py-3"
                  >
                    <Avatar
                      name={getUserFromStore(request.to_user_id)?.username}
                      seed={request.to_user_id}
                      size="sm"
                    />
                    <span className="min-w-0 flex-1 truncate text-sm text-ink-200">
                      {getUserFromStore(request.to_user_id)?.username ?? "…"}
                    </span>
                    <span className="rounded-full border border-white/10 px-2.5 py-1 text-[11px] text-ink-400">
                      Pending
                    </span>
                  </li>
                ))}
              </ul>
            ))}
        </div>
      </div>
    </div>
  );
}
