import type { Guild } from "../../guild/types/guild";
import { useEffect, useState } from "react";
import { fetchGuildById } from "../api/apiClient";

export const GuildIcon = ({ guild }: { guild: string }) => {
  const [guildData, setGuildData] = useState<Guild | null>(null);

  useEffect(() => {
    fetchGuildById(guild)
      .then((res) => {
        setGuildData(res);
      })
      .catch((err) => console.error("Failed to fetch guild", err));
  }, [guild]);

  return (
    <div>
      {guildData?.icon ? (
        <img
          src={guildData.icon}
          alt={guildData.name}
          className="w-full h-full rounded-full"
        />
      ) : (
        <span className="text-white font-bold">{guildData?.name[0]}</span>
      )}
    </div>
  );
};
