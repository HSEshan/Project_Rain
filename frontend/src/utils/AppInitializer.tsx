import { useEffect } from "react";
import { useMessageStore } from "../messages/messageStore";
import { useGuildStore } from "../guild/guildStore";
import { useFriendRequestStore } from "../friends/friendRequestStore";

export default function AppInitializer() {
  const { initialize: initializeMessages } = useMessageStore();
  const { initialize: initializeGuilds } = useGuildStore();
  const { initialize: initializeFriendRequests } = useFriendRequestStore();

  useEffect(() => {
    // Initialize stores after authentication
    const initializeStores = async () => {
      await initializeMessages();
      await initializeGuilds();
      await initializeFriendRequests();
    };
    initializeStores();
  }, [initializeMessages, initializeGuilds, initializeFriendRequests]);

  return null; // This component doesn't render anything
}
