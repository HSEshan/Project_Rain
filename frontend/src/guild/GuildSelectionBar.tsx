import { useGuildStore } from "./guildStore";
import GuildCreateModal from "./GuildCreateModal";
import LinkButton from "../shared/LinkButton";

export default function GuildSelectionBar() {
  const { guilds, setModalOpen } = useGuildStore();

  return (
    <div className="w-1/6 bg-gray-900 text-white flex flex-col items-center px-2 py-4 gap-3">
      Guild Selection Bar
      <button
        className="mt-2 w-full text-sm text-blue-400 hover:underline"
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
          {guild.name}
        </LinkButton>
      ))}
      <GuildCreateModal />
    </div>
  );
}
