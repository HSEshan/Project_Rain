import { useMatch } from "react-router-dom";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import LinkButton from "../shared/LinkButton";
import { useFriendStore } from "../friends/friendStore";
import { PiUserCircle } from "react-icons/pi";

export function MessageSidebar() {
  const { getDMChannels, getParticipants } = useChannelStore();
  const { setIsModalOpen } = useFriendStore();
  const { getUser: getUserFromStore } = useUserStore();
  // dmId belongs to a child route, so it is read from the URL directly
  const dmId = useMatch("/dm/:dmId")?.params.dmId;
  const channels = getDMChannels();

  return (
    <div className="w-1/6 bg-gray-900 text-white flex flex-col items-center px-2 py-4 gap-4">
      <button onClick={() => setIsModalOpen(true)}>Add Friend</button>
      {channels.length === 0 ? (
        <p className="text-sm text-gray-400 text-center">
          No conversations yet
        </p>
      ) : (
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
      )}
    </div>
  );
}
