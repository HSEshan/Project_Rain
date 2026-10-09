import { useEffect } from "react";
import { useChannelStore } from "../shared/channelStore";
import { useGuildStore } from "../guild/guildStore";
import { useUserStore } from "../shared/userStore";
import { useFriendStore } from "../friends/friendStore";
import { useAuth } from "../auth/AuthContext";

export default function AppInitializer() {
  const { fetchUserGuilds, fetchInvites } = useGuildStore();
  const { participants, fetchUserChannels, fetchDMChannelParticipants } =
    useChannelStore();
  const { fetchUsers, mergeUsers } = useUserStore();
  const {
    fetchFriends,
    fetchFriendRequests,
    fetchOutgoingRequests,
    friends,
    friendRequests,
    outgoingRequests,
  } = useFriendStore();

  const selfId = useAuth().getCurrentUser()?.id;

  // Yourself, in the same store as everyone else, so your own avatar renders
  // wherever your id does. The auth cookie carries an id and a name, not a
  // picture.
  useEffect(() => {
    if (selfId) void fetchUsers([selfId]);
  }, [selfId, fetchUsers]);

  useEffect(() => {
    const initializeApp = async () => {
      try {
        await Promise.allSettled([
          fetchUserChannels(),
          fetchUserGuilds(),
          fetchInvites(),
          fetchFriends(),
          fetchFriendRequests(),
          fetchOutgoingRequests(),
        ]);

        await fetchDMChannelParticipants();
      } catch (error) {
        console.error("Failed to initialize app:", error);
      }
    };

    initializeApp();
  }, [
    fetchUserGuilds,
    fetchInvites,
    fetchUserChannels,
    fetchDMChannelParticipants,
    fetchFriends,
    fetchFriendRequests,
    fetchOutgoingRequests,
  ]);

  // The friends endpoint already returns usernames; seed the user store with
  // them so friend rows never flash "Loading...".
  useEffect(() => {
    if (friends.length > 0) mergeUsers(friends);
  }, [friends, mergeUsers]);

  // Everyone else we only know by id has to be looked up in bulk.
  useEffect(() => {
    const users_to_load = Array.from(
      new Set([
        ...Object.values(participants).flat(),
        ...friendRequests.map((friendRequest) => friendRequest.from_user_id),
        ...outgoingRequests.map((friendRequest) => friendRequest.to_user_id),
      ])
    );
    if (users_to_load.length > 0) {
      fetchUsers(users_to_load);
    }
  }, [participants, fetchUsers, friendRequests, outgoingRequests]);

  return null; // This component doesn't render anything
}
