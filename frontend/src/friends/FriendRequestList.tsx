import { useFriendStore } from "./friendStore";
import { useUserStore } from "../shared/userStore";
import { useChannelStore } from "../shared/channelStore";
import { useState } from "react";
import { acceptFriendRequest, rejectFriendRequest } from "./apiClient";

export default function FriendRequestList() {
  const { friendRequests, removeFriendRequest, fetchFriends } = useFriendStore();
  const { getUser: getUserFromStore, fetchUsers } = useUserStore();
  const { fetchUserChannels, setParticipants } = useChannelStore();
  const [response, setResponse] = useState<string>("");

  const namedFriendRequests = friendRequests.map((friendRequest) => {
    return {
      id: friendRequest.id,
      from_user_name:
        getUserFromStore(friendRequest.from_user_id)?.username ?? "Loading...",
    };
  });

  const handleAccept = async (id: string) => {
    try {
      const res = await acceptFriendRequest(id);
      removeFriendRequest(id);
      setResponse("Friend request accepted");

      // The new DM has to show up without a page reload
      const { friend_id, dm_channel_id } = res.data;
      await fetchUserChannels();
      setParticipants(dm_channel_id, [friend_id]);
      await fetchUsers([friend_id]);
      await fetchFriends();
    } catch (error) {
      console.error(error);
      setResponse("Could not accept that friend request");
    }
  };

  const handleReject = async (id: string) => {
    try {
      await rejectFriendRequest(id);
      removeFriendRequest(id);
      setResponse("Friend request rejected");
    } catch (error) {
      console.error(error);
      setResponse("Could not reject that friend request");
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {response && <p className="text-center text-sm">{response}</p>}
      {namedFriendRequests.length === 0 && (
        <p className="text-center text-sm text-gray-400">
          No pending friend requests
        </p>
      )}
      {namedFriendRequests.map((friendRequest) => (
        <div
          key={friendRequest.id}
          className="flex flex-row gap-2  overflow-y-auto h-full"
        >
          <div className="text-sm px-2 py-2 bg-gray-800 rounded-md w-full">
            {friendRequest.from_user_name}
          </div>
          <button
            className="text-sm px-2 py-2 bg-gray-800 rounded-md align-right"
            onClick={() => handleAccept(friendRequest.id)}
          >
            Accept
          </button>
          <button
            className="text-sm px-2 py-2 bg-red-500 rounded-md align-right"
            onClick={() => handleReject(friendRequest.id)}
          >
            Reject
          </button>
        </div>
      ))}
    </div>
  );
}
