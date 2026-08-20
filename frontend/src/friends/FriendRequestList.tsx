import { useState } from "react";
import { FiCheck, FiUserPlus, FiX } from "react-icons/fi";
import { useFriendStore } from "./friendStore";
import { useUserStore } from "../shared/userStore";
import { useChannelStore } from "../shared/channelStore";
import { acceptFriendRequest, rejectFriendRequest } from "./apiClient";
import { errorText } from "../shared/errors";
import Avatar from "../shared/Avatar";
import EmptyState from "../shared/EmptyState";

export default function FriendRequestList() {
  const { friendRequests, removeFriendRequest, fetchFriends } = useFriendStore();
  const { getUser: getUserFromStore, fetchUsers } = useUserStore();
  const { fetchUserChannels, setParticipants } = useChannelStore();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const handleAccept = async (id: string) => {
    setBusy(id);
    setError("");
    try {
      const res = await acceptFriendRequest(id);
      removeFriendRequest(id);

      // The new DM has to show up without a page reload
      const { friend_id, dm_channel_id } = res.data;
      await fetchUserChannels();
      setParticipants(dm_channel_id, [friend_id]);
      await fetchUsers([friend_id]);
      await fetchFriends();
    } catch (err) {
      setError(errorText(err, "Could not accept that request."));
    } finally {
      setBusy(null);
    }
  };

  const handleReject = async (id: string) => {
    setBusy(id);
    setError("");
    try {
      await rejectFriendRequest(id);
      removeFriendRequest(id);
    } catch (err) {
      setError(errorText(err, "Could not reject that request."));
    } finally {
      setBusy(null);
    }
  };

  if (friendRequests.length === 0) {
    return (
      <EmptyState
        icon={<FiUserPlus size={22} />}
        title="No incoming requests"
        hint="When someone adds you, their request lands here in real time."
      />
    );
  }

  return (
    <div className="space-y-1.5">
      {error && (
        <p className="rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
          {error}
        </p>
      )}
      {friendRequests.map((request) => {
        const name =
          getUserFromStore(request.from_user_id)?.username ?? "…";
        return (
          <div
            key={request.id}
            className="flex items-center gap-3 rounded-2xl border border-white/[0.05] bg-white/[0.02] px-4 py-3"
          >
            <Avatar name={name} seed={request.from_user_id} />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-ink-100">
                {name}
              </span>
              <span className="text-xs text-ink-500">
                Sent you a friend request
              </span>
            </span>
            <button
              onClick={() => void handleAccept(request.id)}
              disabled={busy !== null}
              aria-label={`Accept request from ${name}`}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300 transition-colors hover:bg-emerald-500/25 disabled:opacity-40"
            >
              <FiCheck size={16} />
            </button>
            <button
              onClick={() => void handleReject(request.id)}
              disabled={busy !== null}
              aria-label={`Reject request from ${name}`}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/[0.06] text-ink-300 transition-colors hover:bg-red-500/20 hover:text-red-300 disabled:opacity-40"
            >
              <FiX size={16} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
