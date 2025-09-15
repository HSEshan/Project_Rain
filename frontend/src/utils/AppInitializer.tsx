import { useEffect } from "react";
import { useChannelStore } from "../shared/channelStore";
import { useGuildStore } from "../guild/guildStore";
import { useUserStore } from "../shared/userStore";
import { useFriendRequestStore } from "../friends/friendRequestStore";

export default function AppInitializer() {
  const { fetchUserGuilds } = useGuildStore();
  const { participants, fetchUserChannels, fetchDMChannelParticipants } =
    useChannelStore();
  const { fetchUsers } = useUserStore();
  const { fetchFriendRequests, friendRequests } = useFriendRequestStore();

  useEffect(() => {
    const initializeApp = async () => {
      try {
        console.log("Starting app initialization...");

        await Promise.allSettled([
          fetchUserChannels(),
          fetchUserGuilds(),
          fetchFriendRequests(),
        ]);

        await fetchDMChannelParticipants();

        console.log("App initialization completed");
      } catch (error) {
        console.error("Failed to initialize app:", error);
      }
    };

    initializeApp();
  }, [
    fetchUserGuilds,
    fetchUserChannels,
    fetchDMChannelParticipants,
    fetchFriendRequests,
  ]);

  useEffect(() => {
    const users_to_load = Array.from(
      new Set([
        ...Object.values(participants).flat(),
        ...friendRequests.map((friendRequest) => friendRequest.from_user_id),
      ])
    );
    if (users_to_load.length > 0) {
      fetchUsers(users_to_load);
    }
  }, [participants, fetchUsers, friendRequests]);

  return null; // This component doesn't render anything
}
