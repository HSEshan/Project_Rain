import { useGuildStore } from "./guildStore";
import GuildCreateModal from "./GuildCreateModal";
import LinkButton from "../shared/LinkButton";
import { PiShield } from "react-icons/pi";

export default function GuildSelectionBar() {
  const { guilds, setModalOpen } = useGuildStore();

  return (
    <div className="w-1/6 bg-gray-900 text-white flex flex-col items-center px-2 py-4 gap-3">
      <button
        onClick={() => {
          setModalOpen(true);
        }}
      >
        Create Guild
      </button>
      {guilds.map((guild) => (
        <LinkButton
          to={`/guild/${guild.id}`}
          key={guild.id}
          className="w-full h-10 rounded-sm flex items-center justify-center"
        >
          <div className="flex items-center gap-2 w-full px-2">
            <PiShield size={30} className="relative mr-2" />
            {guild.name}
          </div>
        </LinkButton>
      ))}
      <GuildCreateModal />
    </div>
  );
}
