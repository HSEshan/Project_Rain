import { useNavigate } from "react-router-dom";
import {
  FiArrowRight,
  FiMail,
  FiMessageCircle,
  FiPlus,
  FiUserPlus,
  FiUsers,
} from "react-icons/fi";
import { useFriendStore } from "../friends/friendStore";
import { useGuildStore } from "../guild/guildStore";
import { useChannelStore } from "../shared/channelStore";
import { useAuth } from "../auth/AuthContext";
import Avatar from "../shared/Avatar";
import Badge from "../shared/Badge";
import Card from "./Card";
import ViewHeader from "../shared/ViewHeader";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 5) return "Still up";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function HomePage() {
  const { setIsModalOpen: openAddFriend, friendRequests, friends } =
    useFriendStore();
  const {
    setModalOpen: openCreateGuild,
    invites,
    setInviteInboxOpen,
    guilds,
  } = useGuildStore();
  const { getDMChannels } = useChannelStore();
  const { getCurrentUser } = useAuth();
  const navigate = useNavigate();

  const user = getCurrentUser();
  const dmCount = getDMChannels().length;

  const stats = [
    { label: "Friends", value: friends.length, icon: FiUsers },
    { label: "Conversations", value: dmCount, icon: FiMessageCircle },
    { label: "Guilds", value: guilds.length, icon: FiPlus },
  ];

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-ink-950">
      <ViewHeader title="Home" />

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
          <div className="flex items-center gap-4 animate-fade-up">
            <Avatar name={user?.username} seed={user?.id} size="lg" />
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-bold text-white sm:text-3xl">
                {greeting()}, {user?.username ?? "there"}
              </h1>
              <p className="mt-1 text-sm text-ink-400">
                {friendRequests.length + invites.length > 0
                  ? "You have something waiting."
                  : "Everything is quiet. Start a conversation."}
              </p>
            </div>
          </div>

          <dl className="mt-8 grid animate-fade-up grid-cols-3 gap-3 delay-70">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-2xl border border-white/[0.07] bg-white/[0.02] px-4 py-3.5"
              >
                <dt className="flex items-center gap-1.5 text-xs text-ink-400">
                  <stat.icon size={13} /> {stat.label}
                </dt>
                <dd className="mt-1 text-2xl font-semibold text-white">
                  {stat.value}
                </dd>
              </div>
            ))}
          </dl>

          <h2 className="mb-3 mt-10 animate-fade-up text-xs font-semibold uppercase tracking-widest text-ink-400 delay-140">
            Jump in
          </h2>
          <div className="grid animate-fade-up gap-3 delay-140 sm:grid-cols-2">
            <Card
              title="Add a friend"
              body="Send a request by username. Their DM opens the moment they accept."
              icon={<FiUserPlus size={20} />}
              onClick={() => openAddFriend(true)}
            />
            <Card
              title="Create a guild"
              body="Get a text and a voice channel, then invite people in."
              icon={<FiPlus size={20} />}
              onClick={() => openCreateGuild(true)}
            />
            <Card
              title="Friend requests"
              body="People waiting on you to accept."
              icon={<FiUsers size={20} />}
              badge={friendRequests.length}
              onClick={() => navigate("/dm")}
            />
            <Card
              title="Guild invites"
              body="Guilds you have been invited to join."
              icon={<FiMail size={20} />}
              badge={invites.length}
              onClick={() => setInviteInboxOpen(true)}
            />
          </div>

          {guilds.length > 0 && (
            <>
              <h2 className="mb-3 mt-10 text-xs font-semibold uppercase tracking-widest text-ink-400">
                Your guilds
              </h2>
              <div className="flex flex-wrap gap-2">
                {guilds.map((guild) => (
                  <button
                    key={guild.id}
                    onClick={() => navigate(`/guild/${guild.id}`)}
                    className="group flex items-center gap-2.5 rounded-xl border border-white/[0.07] bg-white/[0.02] py-2 pl-2 pr-3.5 transition-all hover:border-rain-400/30 hover:bg-white/[0.05]"
                  >
                    <Avatar name={guild.name} seed={guild.id} size="sm" />
                    <span className="max-w-[12rem] truncate text-sm text-ink-100">
                      {guild.name}
                    </span>
                    <FiArrowRight
                      size={14}
                      className="text-ink-500 transition-transform group-hover:translate-x-0.5 group-hover:text-rain-300"
                    />
                  </button>
                ))}
              </div>
            </>
          )}

          {invites.length > 0 && (
            <button
              onClick={() => setInviteInboxOpen(true)}
              className="gradient-border mt-10 flex w-full items-center gap-3 rounded-2xl bg-gradient-to-r from-rain-400/[0.08] to-transparent px-5 py-4 text-left transition-colors hover:from-rain-400/[0.14]"
            >
              <FiMail className="shrink-0 text-rain-300" size={18} />
              <span className="flex-1 text-sm text-ink-100">
                You have {invites.length} guild{" "}
                {invites.length === 1 ? "invitation" : "invitations"} waiting.
              </span>
              <Badge count={invites.length} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
