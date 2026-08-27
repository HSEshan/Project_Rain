import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FiCheck, FiUsers } from "react-icons/fi";
import Modal from "../shared/Modal";
import Avatar from "../shared/Avatar";
import { Button } from "../shared/Button";
import { Input } from "../shared/Input";
import { errorText } from "../shared/errors";
import { useFriendStore } from "../friends/friendStore";
import { useChannelStore } from "../shared/channelStore";
import { createGroupDM } from "../shared/channelApiClient";
import { useUiStore } from "../shared/uiStore";

/** Discord's ceiling, and the server's. Mirrors MAX_GROUP_DM_MEMBERS in libs. */
const MAX_MEMBERS = 10;

/**
 * Start a group DM by picking friends.
 *
 * Only friends are offered, because that is the server's rule too: you can put
 * your own friends in a group and nobody else. Showing a username field here
 * would invite a 403 for a rule the UI could have expressed instead.
 */
export default function GroupDMCreateModal() {
  const { groupCreateOpen, setGroupCreateOpen } = useUiStore();
  const { friends, fetchFriends } = useFriendStore();
  const { addChannel, refreshChannel } = useChannelStore();
  const navigate = useNavigate();

  const [selected, setSelected] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (groupCreateOpen) void fetchFriends();
  }, [groupCreateOpen, fetchFriends]);

  const close = () => {
    setSelected([]);
    setName("");
    setError("");
    setGroupCreateOpen(false);
  };

  const toggle = (id: string) =>
    setSelected((current) =>
      current.includes(id)
        ? current.filter((selectedId) => selectedId !== id)
        : current.length >= MAX_MEMBERS - 1
        ? current
        : [...current, id]
    );

  const create = async () => {
    setCreating(true);
    setError("");
    try {
      const channel = await createGroupDM(selected, name);
      // Add it locally rather than waiting for the round trip through the
      // event pipeline: the creator is the one person who already knows.
      //
      // The participant list has to come with it. Everyone else learns about
      // this channel through `channels_changed`, which refetches both; the
      // creator does not get that event, so without this the group opens
      // claiming to have one member in it.
      addChannel(channel);
      await refreshChannel(channel.id);
      close();
      navigate(`/dm/${channel.id}`);
    } catch (createError) {
      setError(errorText(createError, "Could not create that group."));
    } finally {
      setCreating(false);
    }
  };

  return (
    <Modal
      isOpen={groupCreateOpen}
      onClose={close}
      title="New group"
      description="Pick at least two friends. Anyone in the group can add more of their own friends later."
    >
      <div className="space-y-4">
        <Input
          label="Group name (optional)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Named after its members if you leave this blank"
          maxLength={80}
        />

        {friends.length === 0 ? (
          <p className="rounded-xl border border-white/[0.06] px-4 py-6 text-center text-sm text-ink-400">
            You need friends before you can start a group. Add someone first.
          </p>
        ) : (
          <div>
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-ink-400">
              Friends ({selected.length} selected)
            </p>
            <ul className="max-h-56 space-y-0.5 overflow-y-auto pr-1">
              {friends.map((friend) => {
                const isSelected = selected.includes(friend.id);
                const atCapacity =
                  !isSelected && selected.length >= MAX_MEMBERS - 1;
                return (
                  <li key={friend.id}>
                    <button
                      type="button"
                      onClick={() => toggle(friend.id)}
                      disabled={atCapacity}
                      className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors disabled:opacity-40 ${
                        isSelected
                          ? "bg-rain-400/10 text-white"
                          : "text-ink-200 hover:bg-white/[0.04]"
                      }`}
                    >
                      <Avatar
                        name={friend.username}
                        seed={friend.id}
                        size="sm"
                      />
                      <span className="min-w-0 flex-1 truncate text-sm">
                        {friend.username}
                      </span>
                      {isSelected && (
                        <FiCheck size={16} className="text-rain-300" />
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {error && <p className="text-xs text-red-300">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button
            variant="primary"
            icon={<FiUsers size={15} />}
            loading={creating}
            disabled={selected.length < 2}
            onClick={create}
          >
            {selected.length < 2
              ? "Pick two or more"
              : `Start group (${selected.length + 1})`}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
