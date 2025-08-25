import { useEffect, useState } from "react";
import { fetchUserGuilds } from "../api/apiClient";
import { eventBus } from "../../shared/events/EventBus";
import { EventType } from "../../shared/events/eventType";
import { useLocation } from "react-router-dom";

export function useSidebarData() {
  const location = useLocation();
  const [guilds, setGuilds] = useState<string[]>([]);
  const [dmUnread, setDmUnread] = useState(0);
  const [guildUnread, setGuildUnread] = useState<Record<string, number>>({});

  useEffect(() => {
    fetchUserGuilds()
      .then((res) => {
        setGuilds(res);
        console.log("Guids: ", res);
      })
      .catch((err) => console.error("Failed to fetch guilds", err));
  }, []);

  useEffect(() => {
    const unsubDM = eventBus.subscribe(EventType.MESSAGE, (event) => {
      const isInDM = location.pathname.startsWith(`/dm/${event.sender_id}`);
      if (!isInDM) setDmUnread((prev) => prev + 1);
    });

    // const unsubGuild = eventBus.subscribe(EventType.MESSAGE, (event) => {
    //   const guildId = event.metadata?.guildId;
    //   const isInGuild = location.pathname.includes(`/guilds/${guildId}`);
    //   if (!isInGuild && guildId) {
    //     setGuildUnread((prev) => ({
    //       ...prev,
    //       [guildId]: (prev[guildId] || 0) + 1,
    //     }));
    //   }
    // });

    return () => {
      unsubDM();
      // unsubGuild();
    };
  }, [location]);

  const resetDMUnread = () => setDmUnread(0);
  const resetGuildUnread = (guildId: string) =>
    setGuildUnread((prev) => ({ ...prev, [guildId]: 0 }));

  return {
    guilds,
    dmUnread,
    guildUnread,
    resetDMUnread,
    resetGuildUnread,
  };
}
