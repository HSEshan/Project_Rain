import { useParams } from "react-router-dom";
import { useMessageStore } from "./messageStore";
import { useEffect } from "react";
import LinkButton from "../shared/LinkButton";
import AddFriendModal from "../friends/AddFriendModal";
import { useFriendRequestStore } from "../friends/friendRequestStore";

export function MessageSidebar() {
  const { channels, unReads, removeUnRead } = useMessageStore();
  const { setIsModalOpen } = useFriendRequestStore();
  const { dmId } = useParams<{ dmId: string }>();

  useEffect(() => {
    removeUnRead(dmId ?? "");
  }, [channels]);

  return (
    <div className="w-1/6 bg-gray-900 text-white flex flex-col items-center px-2 py-4 gap-4">
      <button onClick={() => setIsModalOpen(true)}>Add Friend</button>
      <AddFriendModal />
      {channels.map((channel) => (
        <LinkButton
          to={`/dm/${channel.channel_id}`}
          key={channel.channel_id}
          active={dmId === channel.channel_id}
          unread={unReads.includes(channel.channel_id)}
        >
          {channel.participants
            .map((participant) => participant.username)
            .join(", ")}
        </LinkButton>
      ))}
    </div>
  );
}
