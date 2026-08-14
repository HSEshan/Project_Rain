import { useEffect, useState } from "react";
import Modal from "../shared/Modal";
import { useGuildStore } from "./guildStore";
import { useFriendStore } from "../friends/friendStore";
import { postGuildInvite } from "./apiClient";

type Result = { ok: boolean; text: string } | null;

function errorText(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  // A 422 from the invite schema arrives as a list of validation errors
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return fallback;
}

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
      setResult({ ok: false, text: errorText(error, `Could not invite ${label}`) });
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
    >
      <div className="space-y-5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (username.trim()) void invite({ username: username.trim() }, username.trim());
          }}
        >
          <label
            htmlFor="invite-username"
            className="block text-sm font-medium text-gray-300 mb-2"
          >
            Invite by username
          </label>
          <div className="flex gap-2">
            <input
              id="invite-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              type="submit"
              disabled={!username.trim() || pending !== null}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-md transition-colors"
            >
              Invite
            </button>
          </div>
        </form>

        <div>
          <h4 className="text-sm font-medium text-gray-300 mb-2">Friends</h4>
          {invitable.length === 0 ? (
            <p className="text-sm text-gray-500">
              {friends.length === 0
                ? "You have no friends to invite yet."
                : "All of your friends are already in this guild."}
            </p>
          ) : (
            <ul className="flex flex-col gap-1 max-h-48 overflow-y-auto">
              {invitable.map((friend) => (
                <li
                  key={friend.id}
                  className="flex items-center justify-between gap-2 px-2 py-1 rounded hover:bg-gray-800"
                >
                  <span className="text-sm text-gray-200 truncate">
                    {friend.username}
                  </span>
                  <button
                    type="button"
                    disabled={pending !== null}
                    onClick={() =>
                      void invite({ user_id: friend.id }, friend.username)
                    }
                    className="text-xs px-3 py-1 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white rounded transition-colors"
                  >
                    Invite
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {result && (
          <p
            className={`text-center text-sm ${
              result.ok ? "text-green-400" : "text-red-400"
            }`}
          >
            {result.text}
          </p>
        )}

        <button
          type="button"
          onClick={handleClose}
          className="w-full px-4 py-2 text-gray-300 bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
        >
          Done
        </button>
      </div>
    </Modal>
  );
}
