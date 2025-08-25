import { useEffect, useState } from "react";
import type { Guild } from "../types/guild";
import { fetchUserGuilds } from "../api/apiClient";

export function useGuildData() {
  const [guilds, setGuilds] = useState<Guild[]>([]);

  useEffect(() => {
    fetchUserGuilds()
      .then(setGuilds)
      .catch((err) => console.error("Failed to fetch guilds", err));
  }, []);

  return { guilds };
}
