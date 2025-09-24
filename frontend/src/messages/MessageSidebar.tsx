import { useParams } from "react-router-dom";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import LinkButton from "../shared/LinkButton";
import AddFriendModal from "../friends/AddFriendModal";
import { useFriendRequestStore } from "../friends/friendRequestStore";
import { useEffect } from "react";
import { useMessageStore } from "../shared/messageStore";
import { PiUserCircle } from "react-icons/pi";

export function MessageSidebar() {
  const { getAllChannels, getParticipants } = useChannelStore();
  const { fetchChannelMessages } = useMessageStore();
  const { setIsModalOpen } = useFriendRequestStore();
  const { getUser: getUserFromStore } = useUserStore();
  const { dmId } = useParams<{ dmId: string }>();
  const channels = getAllChannels();

  useEffect(() => {
    if (dmId) {
      fetchChannelMessages(dmId);
    }
  }, [dmId, fetchChannelMessages]);

  return (
    <div className="w-1/6 bg-gray-900 text-white flex flex-col items-center px-2 py-4 gap-4">
      <button onClick={() => setIsModalOpen(true)}>Add Friend</button>
      <AddFriendModal />
      {channels ? (
        channels.map((channel) => (
          <LinkButton
            to={`/dm/${channel.id}`}
            key={channel.id}
            active={dmId === channel.id}
          >
            <div className="flex items-center gap-2 w-full px-2">
              <PiUserCircle size={30} className="relative mr-2" />
              {getParticipants(channel.id)
                .map((participant) => getUserFromStore(participant)?.username)
                .join(", ")}
            </div>
          </LinkButton>
        ))
      ) : (
        <p>No channels</p>
      )}
    </div>
  );
}
