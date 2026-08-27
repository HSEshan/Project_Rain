import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { FiAtSign, FiUsers } from "react-icons/fi";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import { ChannelType } from "../shared/types";
import CallBar, { CallButton } from "../voice/CallBar";
import { MessageView } from "./MessageView";
import GroupDMPanel from "./GroupDMPanel";

/**
 * Route element for /dm/:dmId, for both a two-person DM and a group.
 *
 * The two differ in three places and nowhere else: the title, whether there is
 * a member panel, and the icon. Messages, calls and events are identical, which
 * is why a group DM needed no new view.
 */
export function DMView() {
  const { dmId } = useParams<{ dmId: string }>();
  const { getParticipants, getChannel } = useChannelStore();
  const { getUser: getUserFromStore, fetchUsers } = useUserStore();
  const [membersOpen, setMembersOpen] = useState(false);

  const participants = dmId ? getParticipants(dmId) : [];
  const channel = dmId ? getChannel(dmId) : undefined;
  const isGroup = channel?.type === ChannelType.GROUP_DM;

  // A group's participants may include people no view has loaded yet.
  useEffect(() => {
    if (participants.length > 0) fetchUsers(participants);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [participants.length, fetchUsers]);

  // Closing the panel when moving between channels stops it opening on a
  // two-person DM, which has no roster to manage.
  useEffect(() => {
    setMembersOpen(false);
  }, [dmId]);

  if (!dmId) return null;

  const names = participants
    .map((participantId) => getUserFromStore(participantId)?.username)
    .filter(Boolean)
    .join(", ");

  // A group can be named or unnamed; an unnamed one is titled by who is in it,
  // the way Discord does it.
  const title = (isGroup ? channel?.name || names : names) || "Loading…";

  return (
    <>
      <MessageView
        channelId={dmId}
        title={title}
        icon={isGroup ? <FiUsers size={16} /> : <FiAtSign size={16} />}
        subtitle={
          isGroup ? `Group of ${participants.length + 1}` : "Direct message"
        }
        actions={
          <>
            {/* Top right, where a call button lives in every other chat app.
                The strip above the composer only appears once a call exists. */}
            <CallButton channelId={dmId} />
            {isGroup && (
              <button
                onClick={() => setMembersOpen((open) => !open)}
                aria-label="Members"
                className="rounded-lg p-2 text-ink-300 transition-colors hover:bg-white/5 hover:text-white"
              >
                <FiUsers size={17} />
              </button>
            )}
          </>
        }
        aboveComposer={<CallBar channelId={dmId} />}
      />

      {isGroup && membersOpen && (
        <GroupDMPanel channelId={dmId} onClose={() => setMembersOpen(false)} />
      )}
    </>
  );
}
