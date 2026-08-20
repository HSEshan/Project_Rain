import { useNavigate } from "react-router-dom";
import { FiArrowRight, FiPlus, FiUsers } from "react-icons/fi";
import { useGuildStore } from "./guildStore";
import { useChannelStore } from "../shared/channelStore";
import Avatar from "../shared/Avatar";
import { Button } from "../shared/Button";
import EmptyState from "../shared/EmptyState";
import ViewHeader from "../shared/ViewHeader";
import GuildInviteList from "./GuildInviteList";

/** Route element for /guild — the guild picker with nothing selected yet. */
export default function GuildsHome() {
  const { guilds, setModalOpen, invites } = useGuildStore();
  const { getGuildChannels } = useChannelStore();
  const navigate = useNavigate();

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-ink-950">
      <ViewHeader
        icon={<FiUsers size={16} />}
        title="Guilds"
        actions={
          <Button
            size="sm"
            variant="primary"
            icon={<FiPlus size={14} />}
            onClick={() => setModalOpen(true)}
          >
            <span className="hidden sm:inline">Create guild</span>
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
          {invites.length > 0 && (
            <div className="mb-8">
              <GuildInviteList />
            </div>
          )}

          {guilds.length === 0 ? (
            <EmptyState
              icon={<FiUsers size={22} />}
              title="No guilds yet"
              hint="A guild is a space with text and voice channels. Create one, or wait for an invitation to land here."
              action={
                <Button
                  variant="primary"
                  icon={<FiPlus size={14} />}
                  onClick={() => setModalOpen(true)}
                >
                  Create a guild
                </Button>
              }
            />
          ) : (
            <>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-ink-400">
                Your guilds ({guilds.length})
              </h2>
              <div className="grid gap-2.5 sm:grid-cols-2">
                {guilds.map((guild) => {
                  const channels = getGuildChannels(guild.id);
                  return (
                    <button
                      key={guild.id}
                      onClick={() => navigate(`/guild/${guild.id}`)}
                      className="group flex items-center gap-3.5 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4 text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-rain-400/30 hover:bg-white/[0.05]"
                    >
                      <Avatar name={guild.name} seed={guild.id} size="lg" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-semibold text-white">
                          {guild.name}
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-ink-400">
                          {guild.description || `${channels.length} channels`}
                        </span>
                      </span>
                      <FiArrowRight
                        size={16}
                        className="shrink-0 text-ink-500 transition-transform group-hover:translate-x-0.5 group-hover:text-rain-300"
                      />
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
