import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FiMessageSquare, FiUserPlus } from "react-icons/fi";
import Avatar from "../shared/Avatar";
import { Button } from "../shared/Button";
import Modal from "../shared/Modal";
import Spinner from "../shared/Spinner";
import { errorText } from "../shared/errors";
import { createFriendRequest } from "../friends/apiClient";
import { useProfileStore } from "./profileStore";
import { FriendState } from "./apiClient";

const JOINED = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

/**
 * Who someone is, from anywhere their name appears.
 *
 * Mounted once in `MainLayout` and driven by `profileStore`, like every other
 * modal here. The relationship line is the point of it: the same card tells you
 * you are already friends, that you have a request waiting from them, or that
 * you have never met, and offers exactly the action that fits.
 */
export default function ProfileCard() {
  const { userId, profile, loading, error, close, refresh } = useProfileStore();
  const navigate = useNavigate();
  const [sending, setSending] = useState(false);
  const [actionError, setActionError] = useState("");

  const isOpen = !!userId;

  const sendFriendRequest = async () => {
    if (!profile) return;
    setSending(true);
    setActionError("");
    try {
      await createFriendRequest(profile.username);
      // Refetch rather than patching the state locally: the server decides what
      // the relationship is now, and it may have moved for another reason.
      await refresh();
    } catch (requestError) {
      setActionError(errorText(requestError, "Could not send that request."));
    } finally {
      setSending(false);
    }
  };

  const openDM = () => {
    if (!profile?.dm_channel_id) return;
    close();
    navigate(`/dm/${profile.dm_channel_id}`);
  };

  return (
    <Modal isOpen={isOpen} onClose={close} title="Profile">
      {loading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {!loading && error && <p className="py-6 text-sm text-red-300">{error}</p>}

      {!loading && profile && (
        <div className="space-y-5">
          <div className="flex items-center gap-4">
            <Avatar name={profile.username} seed={profile.id} size="xl" />
            <div className="min-w-0">
              <p className="truncate text-xl font-semibold text-white">
                {profile.username}
              </p>
              <p className="text-xs text-ink-400">
                Joined {JOINED(profile.created_at)}
              </p>
              <p className="mt-1 text-xs text-ink-300">
                {RELATIONSHIP[profile.friend_state]}
              </p>
            </div>
          </div>

          {profile.mutual_guilds.length > 0 && (
            <div>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-ink-400">
                Servers in common
              </p>
              <div className="flex flex-wrap gap-1.5">
                {profile.mutual_guilds.map((guild) => (
                  <span
                    key={guild.id}
                    className="rounded-lg border border-white/[0.07] bg-white/[0.04] px-2 py-1 text-xs text-ink-200"
                  >
                    {guild.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {actionError && <p className="text-xs text-red-300">{actionError}</p>}

          {profile.friend_state !== FriendState.SELF && (
            <div className="flex flex-wrap gap-2">
              {profile.dm_channel_id && (
                <Button
                  variant="primary"
                  icon={<FiMessageSquare size={15} />}
                  onClick={openDM}
                >
                  Message
                </Button>
              )}
              {profile.friend_state === FriendState.NONE && (
                <Button
                  variant="secondary"
                  icon={<FiUserPlus size={15} />}
                  loading={sending}
                  onClick={sendFriendRequest}
                >
                  Add friend
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

const RELATIONSHIP: Record<FriendState, string> = {
  [FriendState.SELF]: "This is you.",
  [FriendState.FRIENDS]: "You are friends.",
  [FriendState.REQUEST_SENT]: "Friend request sent, waiting on them.",
  [FriendState.REQUEST_RECEIVED]:
    "They sent you a friend request. Answer it on the Friends page.",
  [FriendState.NONE]: "You are not friends yet.",
};
