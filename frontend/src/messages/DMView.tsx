import { useParams } from "react-router-dom";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import { MessageView } from "./MessageView";

/** Route element for /dm/:dmId — titles the chat with the other participants. */
export function DMView() {
  const { dmId } = useParams<{ dmId: string }>();
  const { getParticipants } = useChannelStore();
  const { getUser: getUserFromStore } = useUserStore();

  if (!dmId) return null;

  const names = getParticipants(dmId)
    .map((participantId) => getUserFromStore(participantId)?.username)
    .filter(Boolean)
    .join(", ");

  return <MessageView channelId={dmId} title={names || "Loading..."} />;
}
