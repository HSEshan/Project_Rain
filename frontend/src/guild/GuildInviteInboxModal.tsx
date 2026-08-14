import Modal from "../shared/Modal";
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
    >
      <div className="space-y-5">
        <GuildInviteList
          onAccepted={() => setInviteInboxOpen(false)}
          emptyState={
            <p className="text-sm text-gray-500">
              No pending guild invitations.
            </p>
          }
        />
        <button
          type="button"
          onClick={() => setInviteInboxOpen(false)}
          className="w-full px-4 py-2 text-gray-300 bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
        >
          Done
        </button>
      </div>
    </Modal>
  );
}
