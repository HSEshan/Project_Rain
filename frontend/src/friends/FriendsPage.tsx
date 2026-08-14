import { useNavigate } from "react-router-dom";
import { useFriendStore } from "./friendStore";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import FriendRequestList from "./FriendRequestList";
import { PiUserCircle } from "react-icons/pi";

/** Landing panel for /dm — friends, incoming requests and outgoing requests. */
export default function FriendsPage() {
  const { friends, outgoingRequests, setIsModalOpen } = useFriendStore();
  const { getDMChannelWithUser } = useChannelStore();
  const { getUser: getUserFromStore } = useUserStore();
  const navigate = useNavigate();

  const openDM = (userId: string) => {
    const channel = getDMChannelWithUser(userId);
    if (channel) navigate(`/dm/${channel.id}`);
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 text-white">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Friends</h1>
        <button
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
          onClick={() => setIsModalOpen(true)}
        >
          Add Friend
        </button>
      </div>

      <section className="mb-8">
        <h2 className="text-xs uppercase tracking-wide text-gray-400 mb-2">
          All friends — {friends.length}
        </h2>
        {friends.length === 0 ? (
          <p className="text-sm text-gray-500">
            No friends yet. Add someone by username to get started.
          </p>
        ) : (
          <div className="flex flex-col gap-1">
            {friends.map((friend) => (
              <div
                key={friend.id}
                className="flex items-center gap-3 px-3 py-2 bg-gray-900 rounded-md"
              >
                <PiUserCircle size={28} />
                <span className="flex-1 truncate">{friend.username}</span>
                <button
                  className="text-sm px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded-md transition-colors disabled:opacity-40"
                  onClick={() => openDM(friend.id)}
                  disabled={!getDMChannelWithUser(friend.id)}
                >
                  Message
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="mb-8">
        <h2 className="text-xs uppercase tracking-wide text-gray-400 mb-2">
          Incoming requests
        </h2>
        <FriendRequestList />
      </section>

      <section>
        <h2 className="text-xs uppercase tracking-wide text-gray-400 mb-2">
          Sent requests — {outgoingRequests.length}
        </h2>
        {outgoingRequests.length === 0 ? (
          <p className="text-sm text-gray-500">No pending sent requests</p>
        ) : (
          <div className="flex flex-col gap-1">
            {outgoingRequests.map((request) => (
              <div
                key={request.id}
                className="flex items-center gap-3 px-3 py-2 bg-gray-900 rounded-md text-sm"
              >
                <PiUserCircle size={24} />
                <span className="flex-1 truncate">
                  {getUserFromStore(request.to_user_id)?.username ??
                    "Loading..."}
                </span>
                <span className="text-gray-500">pending</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
