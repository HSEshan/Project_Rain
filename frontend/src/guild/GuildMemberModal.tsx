import { useState } from "react";
import Modal from "../shared/Modal";
import { Button } from "../shared/Button";
import { errorText } from "../shared/errors";
import { useUserStore } from "../shared/userStore";
import {
  deleteGuildMember,
  patchGuildMemberRole,
  postGuildBan,
  postTransferGuild,
} from "./apiClient";
import { useGuildStore } from "./guildStore";
import {
  GuildPermission,
  allows,
  assignableRoles,
  useGuildStanding,
} from "./permissions";
import { GuildMemberRole, type GuildMember } from "./types";

const ROLE_COPY: Record<GuildMemberRole, { label: string; hint: string }> = {
  [GuildMemberRole.MEMBER]: { label: "Member", hint: "Can talk and invite" },
  [GuildMemberRole.MODERATOR]: {
    label: "Moderator",
    hint: "Can also remove members and delete their messages",
  },
  [GuildMemberRole.ADMIN]: {
    label: "Admin",
    hint: "Can also manage channels, roles and the guild",
  },
};

/**
 * Change one person's role, or remove them. Only opened for someone the viewer
 * outranks, so what is offered here is what the server will accept.
 */
export default function GuildMemberModal({
  guildId,
  member,
  onClose,
}: {
  guildId: string;
  member: GuildMember | null;
  onClose: () => void;
}) {
  const standing = useGuildStanding(guildId);
  const { setMember, removeMember, replaceGuild, fetchGuildMembers } =
    useGuildStore();
  const username = useUserStore(
    (state) => state.users[member?.user_id ?? ""]?.username
  );
  const [busy, setBusy] = useState(false);
  // Remove and ban share one confirmation: the second question is the same one
  const [confirming, setConfirming] = useState<"remove" | "ban" | null>(null);
  const [confirmingTransfer, setConfirmingTransfer] = useState(false);
  const [error, setError] = useState("");

  const close = () => {
    setConfirming(null);
    setConfirmingTransfer(false);
    setError("");
    setBusy(false);
    onClose();
  };

  if (!member) return null;

  const changeRole = async (role: GuildMemberRole) => {
    if (role === member.role) return;
    setBusy(true);
    setError("");
    try {
      // The actor's own response is the news: set it here rather than waiting
      setMember(await patchGuildMemberRole(guildId, member.user_id, role));
      close();
    } catch (err) {
      setError(errorText(err, "Could not change that role."));
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setError("");
    try {
      if (confirming === "ban") {
        await postGuildBan(guildId, member.user_id);
      } else {
        await deleteGuildMember(guildId, member.user_id);
      }
      removeMember(guildId, member.user_id);
      close();
    } catch (err) {
      setError(errorText(err, "Could not remove that member."));
      setBusy(false);
    }
  };

  const transfer = async () => {
    setBusy(true);
    setError("");
    try {
      replaceGuild(await postTransferGuild(guildId, member.user_id));
      // Their row changed as well as the guild's
      await fetchGuildMembers(guildId);
      close();
    } catch (err) {
      setError(errorText(err, "Could not transfer the guild."));
      setBusy(false);
    }
  };

  return (
    <Modal isOpen onClose={close} title={username ?? "Member"}>
      <div className="space-y-5">
        {allows(standing, GuildPermission.MANAGE_ROLES) && (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-300">
              Role
            </p>
            {assignableRoles(standing).map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => void changeRole(role)}
                disabled={busy}
                aria-pressed={member.role === role}
                className={`flex w-full flex-col items-start gap-0.5 rounded-xl border p-3 text-left transition-all ${
                  member.role === role
                    ? "border-rain-400/40 bg-rain-400/[0.08] text-white"
                    : "border-white/[0.07] bg-white/[0.02] text-ink-300 hover:border-white/15"
                }`}
              >
                <span className="text-sm font-medium">
                  {ROLE_COPY[role].label}
                </span>
                <span className="text-[11px] text-ink-400">
                  {ROLE_COPY[role].hint}
                </span>
              </button>
            ))}
          </div>
        )}

        {error && (
          <p className="rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
            {error}
          </p>
        )}

        {allows(standing, GuildPermission.TRANSFER_OWNERSHIP) &&
          (confirmingTransfer ? (
            <div className="space-y-3">
              <p className="text-sm text-ink-300">
                Give this guild to {username ?? "this member"}? You stay an admin,
                but only they can undo this.
              </p>
              <div className="flex gap-3">
                <Button
                  type="button"
                  onClick={() => setConfirmingTransfer(false)}
                  disabled={busy}
                  full
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => void transfer()}
                  loading={busy}
                  full
                >
                  Transfer
                </Button>
              </div>
            </div>
          ) : (
            <Button
              type="button"
              onClick={() => setConfirmingTransfer(true)}
              disabled={busy}
              full
            >
              Transfer ownership
            </Button>
          ))}

        {allows(standing, GuildPermission.KICK) &&
          (confirming ? (
            <div className="space-y-3">
              <p className="text-sm text-ink-300">
                {confirming === "ban"
                  ? `Ban ${username ?? "this member"}? They are removed, and no invite will let them back in until the ban is lifted.`
                  : `Remove ${username ?? "this member"} from the guild? They can come back with a new invite.`}
              </p>
              <div className="flex gap-3">
                <Button
                  type="button"
                  onClick={() => setConfirming(null)}
                  disabled={busy}
                  full
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => void remove()}
                  loading={busy}
                  full
                >
                  {confirming === "ban" ? "Ban" : "Remove"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-3">
              <Button
                type="button"
                variant="danger"
                onClick={() => setConfirming("remove")}
                disabled={busy}
                full
              >
                Remove
              </Button>
              <Button
                type="button"
                variant="danger"
                onClick={() => setConfirming("ban")}
                disabled={busy}
                full
              >
                Ban
              </Button>
            </div>
          ))}
      </div>
    </Modal>
  );
}
