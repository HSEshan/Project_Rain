import { useEffect, useState } from "react";
import { FiAtSign, FiUserPlus } from "react-icons/fi";
import Modal from "../shared/Modal";
import Avatar from "../shared/Avatar";
import { Button } from "../shared/Button";
import { Input } from "../shared/Input";
import { errorText } from "../shared/errors";
import { useGuildStore } from "./guildStore";
import { useFriendStore } from "../friends/friendStore";
import { postGuildInvite } from "./apiClient";

type Result = { ok: boolean; text: string } | null;

export default function GuildInviteModal() {
  const { inviteModalGuildId, setInviteModalGuildId, getGuild, getMembers } =
    useGuildStore();
  const { friends, fetchFriends } = useFriendStore();
  const [username, setUsername] = useState("");
  const [result, setResult] = useState<Result>(null);
  const [pending, setPending] = useState<string | null>(null);

  const guildId = inviteModalGuildId;
  const guild = getGuild(guildId ?? "");
  const memberIds = new Set(getMembers(guildId ?? "").map((m) => m.user_id));
  // Someone already in the guild cannot be invited again, so do not offer it
  const invitable = friends.filter((friend) => !memberIds.has(friend.id));

  useEffect(() => {
    if (guildId) void fetchFriends();
  }, [guildId, fetchFriends]);

  const invite = async (
    target: { username: string } | { user_id: string },
    label: string
  ) => {
    if (!guildId) return;
    setPending(label);
    try {
      await postGuildInvite(guildId, target);
      setResult({ ok: true, text: `Invited ${label}` });
      setUsername("");
    } catch (error) {
      setResult({
        ok: false,
        text: errorText(error, `Could not invite ${label}`),
      });
    } finally {
      setPending(null);
    }
  };

  const handleClose = () => {
    setResult(null);
    setUsername("");
    setInviteModalGuildId(null);
  };

  return (
    <Modal
      isOpen={guildId !== null}
      onClose={handleClose}
      title={guild ? `Invite to ${guild.name}` : "Invite"}
      description="They will see the invitation the moment you send it."
    >
      <div className="space-y-5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const name = username.trim();
            if (name) void invite({ username: name }, name);
          }}
        >
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Input
                label="Invite by username"
                name="invite-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter a username"
                icon={<FiAtSign size={15} />}
              />
            </div>
            <Button
              type="submit"
              variant="primary"
              disabled={!username.trim()}
              loading={pending === username.trim() && !!username.trim()}
            >
              Invite
            </Button>
          </div>
        </form>

        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-300">
            From your friends
          </h4>
          {invitable.length === 0 ? (
            <p className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-5 text-center text-sm text-ink-400">
              {friends.length === 0
                ? "You have no friends to invite yet."
                : "All of your friends are already in this guild."}
            </p>
          ) : (
            <ul className="max-h-52 space-y-1 overflow-y-auto">
              {invitable.map((friend) => (
                <li
                  key={friend.id}
                  className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 transition-colors hover:bg-white/[0.04]"
                >
                  <Avatar name={friend.username} seed={friend.id} size="sm" />
                  <span className="min-w-0 flex-1 truncate text-sm text-ink-200">
                    {friend.username}
                  </span>
                  <Button
                    size="sm"
                    icon={<FiUserPlus size={13} />}
                    disabled={pending !== null}
                    loading={pending === friend.username}
                    onClick={() =>
                      void invite({ user_id: friend.id }, friend.username)
                    }
                  >
                    Invite
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {result && (
          <p
            className={`rounded-xl border px-3.5 py-2.5 text-center text-sm ${
              result.ok
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                : "border-red-500/25 bg-red-500/10 text-red-300"
            }`}
          >
            {result.text}
          </p>
        )}

        <Button full onClick={handleClose}>
          Done
        </Button>
      </div>
    </Modal>
  );
}
