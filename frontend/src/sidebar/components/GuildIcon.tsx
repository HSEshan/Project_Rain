import type { Guild } from "../../types/guild";

export const GuildIcon = ({ guild }: { guild: Guild }) => {
  return (
    <div>
      {guild.icon ? (
        <img
          src={guild.icon}
          alt={guild.name}
          className="w-full h-full rounded-full"
        />
      ) : (
        <span className="text-white font-bold">{guild.name[0]}</span>
      )}
    </div>
  );
};
