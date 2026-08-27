import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FiEdit2, FiLogOut, FiUserPlus, FiX } from "react-icons/fi";
import Avatar from "../shared/Avatar";
import { Button } from "../shared/Button";
import { Input } from "../shared/Input";
import { errorText } from "../shared/errors";
import { useChannelStore } from "../shared/channelStore";
import {
  addGroupDMMember,
  leaveGroupDM,
  renameGroupDM,
} from "../shared/channelApiClient";
import { useFriendStore } from "../friends/friendStore";
import ProfileTrigger from "../profile/ProfileTrigger";
import { useGroupDMStore } from "./groupDMStore";

/**
 * Members of a group DM, plus the three things you can do to one: rename it,
 * add a friend, or leave.
 *
 * There is no "remove member". A group DM has no roles, so a remove button
 * would be held equally by everyone in the room; the server does not implement
 * one either. Leaving is the only exit, and the last person out deletes the
 * channel.
 */
export default function GroupDMPanel({
  channelId,
  onClose,
}: {
  channelId: string;
  onClose: () => void;
}) {
  const { getMembers, fetchMembers, setMembers, forget } = useGroupDMStore();
  const { getChannel, addChannel, removeChannel, refreshChannel } =
    useChannelStore();
  const { friends, fetchFriends } = useFriendStore();
  const navigate = useNavigate();

  const members = getMembers(channelId);
  const channel = getChannel(channelId);

  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(channel?.name ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void fetchMembers(channelId);
    void fetchFriends();
  }, [channelId, fetchMembers, fetchFriends]);

  useEffect(() => {
    setName(channel?.name ?? "");
  }, [channel?.name]);

  const memberIds = new Set(members.map((member) => member.user_id));
  const addable = friends.filter((friend) => !memberIds.has(friend.id));

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (actionError) {
      setError(errorText(actionError, "That did not work."));
    } finally {
      setBusy(false);
    }
  };

  /**
   * Every action here applies its own result locally as well as calling the
   * server. `group_dm_updated` is published to the *other* members and not to
   * whoever caused it, which is right (they already know) but means the actor
   * is the one client that will not be told. Without these the person who just
   * renamed the group watches the old name stay in the header.
   */
  const submitRename = () =>
    run(async () => {
      addChannel(await renameGroupDM(channelId, name.trim()));
      setRenaming(false);
    });

  const add = (userId: string) =>
    run(async () => {
      setMembers(channelId, await addGroupDMMember(channelId, userId));
      // The header counts participants, which live in the channel store.
      await refreshChannel(channelId);
    });

  const leave = () =>
    run(async () => {
      await leaveGroupDM(channelId);
      // Drop it locally straight away. The server also publishes the change,
      // but the user is standing in a channel they are no longer a member of.
      forget(channelId);
      removeChannel(channelId);
      navigate("/dm");
    });

  return (
    <>
      {/* Below `xl` this is a drawer, the same way the guild members list is:
          a third inline column leaves a phone with no room for the chat. */}
      <div
        className="fixed inset-0 z-30 bg-ink-950/70 backdrop-blur-sm animate-fade-in xl:hidden"
        onClick={onClose}
        role="presentation"
      />

      <aside
        aria-label="Group members"
        className="fixed inset-y-0 right-0 z-40 flex w-64 shrink-0 flex-col border-l border-white/[0.06] bg-ink-900 px-2 pb-4 xl:static xl:z-auto xl:bg-ink-900/40"
      >
        <div className="flex h-14 shrink-0 items-center justify-between px-2">
          <span className="text-sm font-semibold text-white">
            Members ({members.length})
          </span>
          <button
            onClick={onClose}
            aria-label="Close members"
            className="rounded-lg p-2 text-ink-400 hover:bg-white/5 hover:text-white"
          >
            <FiX size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <ul className="space-y-0.5">
            {members.map((member) => (
              <li key={member.user_id}>
                <ProfileTrigger
                  userId={member.user_id}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.04]"
                >
                  <Avatar
                    name={member.username}
                    seed={member.user_id}
                    size="sm"
                  />
                  <span className="min-w-0 flex-1 truncate text-sm text-ink-200">
                    {member.username}
                  </span>
                  {member.is_owner && (
                    <span className="rounded-md bg-rain-400/15 px-1.5 py-0.5 text-[10px] font-medium text-rain-300">
                      owner
                    </span>
                  )}
                </ProfileTrigger>
              </li>
            ))}
          </ul>

          {addable.length > 0 && (
            <div className="mt-4">
              <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-widest text-ink-400">
                Add a friend
              </p>
              <ul className="space-y-0.5">
                {addable.map((friend) => (
                  <li key={friend.id}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => add(friend.id)}
                      className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-sm text-ink-300 transition-colors hover:bg-white/[0.04] hover:text-white disabled:opacity-50"
                    >
                      <FiUserPlus size={14} className="shrink-0 text-ink-500" />
                      <span className="min-w-0 flex-1 truncate">
                        {friend.username}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {error && <p className="px-2 pb-2 text-xs text-red-300">{error}</p>}

        <div className="space-y-2 px-2 pt-2">
          {renaming ? (
            <div className="space-y-2">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Group name"
                maxLength={80}
                autoFocus
              />
              <div className="flex gap-2">
                <Button size="sm" variant="primary" loading={busy} onClick={submitRename}>
                  Save
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setRenaming(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              full
              icon={<FiEdit2 size={13} />}
              onClick={() => setRenaming(true)}
            >
              Rename group
            </Button>
          )}

          <Button
            size="sm"
            variant="danger"
            full
            icon={<FiLogOut size={13} />}
            loading={busy}
            onClick={leave}
          >
            Leave group
          </Button>
        </div>
      </aside>
    </>
  );
}
