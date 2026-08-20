import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FiMail } from "react-icons/fi";
import { useGuildStore } from "./guildStore";
import type { GuildInvite } from "./apiClient";
import Avatar from "../shared/Avatar";
import { Button } from "../shared/Button";
import { errorText } from "../shared/errors";

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

  const respond = async (inviteId: string, accepted: boolean) => {
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
    } catch (err) {
      setError(
        errorText(
          err,
          accepted
            ? `Could not join ${invite.guild_name}. The invite may have expired.`
            : `Could not decline the invitation to ${invite.guild_name}.`
        )
      );
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-2">
      <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-ink-400">
        <FiMail size={13} /> Invitations ({invites.length})
      </h2>

      <ul className="space-y-2">
        {invites.map((invite) => (
          <li
            key={invite.invite_id}
            className="gradient-border flex items-center gap-3 rounded-2xl bg-gradient-to-r from-rain-400/[0.06] to-transparent p-3.5"
          >
            <Avatar name={invite.guild_name} seed={invite.guild_id} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-white">
                {invite.guild_name}
              </p>
              <p className="truncate text-xs text-ink-400">
                {invite.inviter_username
                  ? `Invited by ${invite.inviter_username}`
                  : "Invitation"}
                {" · "}
                {expiresIn(invite)}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button
                size="sm"
                variant="primary"
                loading={busy === invite.invite_id}
                disabled={busy !== null}
                onClick={() => void respond(invite.invite_id, true)}
              >
                Accept
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy !== null}
                onClick={() => void respond(invite.invite_id, false)}
              >
                Decline
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {error && (
        <p className="rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}
