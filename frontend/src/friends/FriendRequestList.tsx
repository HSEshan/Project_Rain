import { useFriendRequestStore } from "./friendRequestStore";
import { useUserStore } from "../shared/userStore";
import { useState } from "react";
import { acceptFriendRequest, rejectFriendRequest } from "./apiClient";

export default function FriendRequestList() {
  const { friendRequests, removeFriendRequest } = useFriendRequestStore();
  const { getUser: getUserFromStore } = useUserStore();
  const [response, setResponse] = useState<string>("");

  const namedFriendRequests = friendRequests.map((friendRequest) => {
    return {
      id: friendRequest.id,
      from_user_name: getUserFromStore(friendRequest.from_user_id)?.username,
    };
  });
  const handleAccept = (id: string) => {
    acceptFriendRequest(id)
      .then((res) => {
        if (res.status === 200) {
          setResponse("Friend request accepted");
          removeFriendRequest(id);
        }
      })
      .catch((error) => {
        console.error(error);
      });
  };
  const handleReject = (id: string) => {
    rejectFriendRequest(id)
      .then((res) => {
        if (res.status === 200) {
          setResponse("Friend request rejected");
          removeFriendRequest(id);
        }
      })
      .catch((error) => {
        console.error(error);
      });
  };
  return (
    <div className="flex flex-col gap-2">
      {response && <p className="text-center text-sm">{response}</p>}
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
