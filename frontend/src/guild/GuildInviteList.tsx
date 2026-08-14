import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGuildStore } from "./guildStore";
import type { GuildInvite } from "./apiClient";

/** Days left before an invite expires, floored at 0. */
function expiresIn(invite: GuildInvite): string {
  const ms = new Date(invite.expires_at).getTime() - Date.now();
  if (Number.isNaN(ms)) return "";
  const days = Math.floor(ms / 86_400_000);
  if (days > 0) return `Expires in ${days} day${days === 1 ? "" : "s"}`;
  const hours = Math.max(0, Math.floor(ms / 3_600_000));
  return `Expires in ${hours} hour${hours === 1 ? "" : "s"}`;
}

interface GuildInviteListProps {
  /** Called after a successful accept — lets a modal close itself. */
  onAccepted?: (invite: GuildInvite) => void;
  /** Rendered instead of nothing when there is no invite waiting. */
  emptyState?: React.ReactNode;
}

/**
 * Guild invitations waiting for this user, with the two things you can do
 * about one. The list is fetched by `AppInitializer` rather than only listened
 * for, so an invite sent while you were offline is not lost.
 */
export default function GuildInviteList({
  onAccepted,
  emptyState,
}: GuildInviteListProps) {
  const { invites, acceptInvite, declineInvite } = useGuildStore();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  if (invites.length === 0) return <>{emptyState ?? null}</>;

  const respond = async (
    inviteId: string,
    accepted: boolean
  ): Promise<void> => {
    const invite = invites.find((i) => i.invite_id === inviteId);
    if (!invite) return;
    setBusy(inviteId);
    setError(null);
    try {
      if (accepted) {
        await acceptInvite(invite);
        onAccepted?.(invite);
        navigate(`/guild/${invite.guild_id}`);
      } else {
        await declineInvite(invite);
      }
    } catch {
      setError(
        accepted
          ? `Could not join ${invite.guild_name}. The invite may have expired.`
          : `Could not decline the invitation to ${invite.guild_name}.`
      );
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="w-full max-w-md flex flex-col gap-2">
      <h2 className="text-xs uppercase tracking-wide text-gray-400">
        Invitations — {invites.length}
      </h2>
      <ul className="flex flex-col gap-2">
        {invites.map((invite) => (
          <li
            key={invite.invite_id}
            className="flex items-center justify-between gap-3 bg-gray-900 rounded-md px-3 py-2"
          >
            <div className="min-w-0">
              <p className="text-sm text-white truncate">{invite.guild_name}</p>
              <p className="text-xs text-gray-400 truncate">
                {invite.inviter_username
                  ? `Invited by ${invite.inviter_username}`
                  : "Invitation"}
              </p>
              <p className="text-xs text-gray-500">{expiresIn(invite)}</p>
            </div>
            <div className="flex gap-2 flex-shrink-0">
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => void respond(invite.invite_id, true)}
                className="text-xs px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded transition-colors"
              >
                {busy === invite.invite_id ? "…" : "Accept"}
              </button>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => void respond(invite.invite_id, false)}
                className="text-xs px-3 py-1 bg-gray-700 hover:bg-red-600 disabled:bg-gray-600 text-white rounded transition-colors"
              >
                Decline
              </button>
            </div>
          </li>
        ))}
      </ul>
      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  );
}
