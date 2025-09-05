import { useEffect } from "react";
import { useMessageStore } from "../messages/messageStore";
import { useGuildStore } from "../guild/guildStore";

export default function AppInitializer() {
  const { initialize: initializeMessages } = useMessageStore();
  const { initialize: initializeGuilds } = useGuildStore();

  useEffect(() => {
    // Initialize stores after authentication
    const initializeStores = async () => {
      await initializeMessages();
      await initializeGuilds();
    };
    initializeStores();
  }, [initializeMessages, initializeGuilds]);

  return null; // This component doesn't render anything
}
