import Modal from "../shared/Modal";
import { Button } from "../shared/Button";
import GuildInviteList from "./GuildInviteList";
import { useGuildStore } from "./guildStore";

/**
 * The receiving half of guild invites, reachable from anywhere.
 *
 * The inline list on `/guild` is only visible when no guild is selected, so a
 * user who is already in a guild had no way to see an invitation. This is
 * driven by store state and mounted once in `MainLayout`, like every other
 * modal.
 */
export default function GuildInviteInboxModal() {
  const { inviteInboxOpen, setInviteInboxOpen } = useGuildStore();

  return (
    <Modal
      isOpen={inviteInboxOpen}
      onClose={() => setInviteInboxOpen(false)}
      title="Guild invitations"
      description="Guilds you have been invited to join."
    >
      <div className="space-y-5">
        <GuildInviteList
          onAccepted={() => setInviteInboxOpen(false)}
          emptyState={
            <p className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-6 text-center text-sm text-ink-400">
              No pending guild invitations.
            </p>
          }
        />
        <Button full onClick={() => setInviteInboxOpen(false)}>
          Done
        </Button>
      </div>
    </Modal>
  );
}
