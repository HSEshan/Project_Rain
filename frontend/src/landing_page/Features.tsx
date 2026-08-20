import {
  FiMessageSquare,
  FiUsers,
  FiMic,
  FiZap,
  FiLayers,
  FiShield,
} from "react-icons/fi";
import Reveal from "./Reveal";

const FEATURES = [
  {
    icon: FiMessageSquare,
    title: "Direct messages",
    body: "Friend requests, accepts, and a DM channel that exists the moment the request is accepted, with no refresh or reconnect.",
  },
  {
    icon: FiUsers,
    title: "Guilds and channels",
    body: "Create a guild, get text and voice channels, and invite people by username or from your friends list. Members appear live.",
  },
  {
    icon: FiMic,
    title: "Group voice on an SFU",
    body: "Self-hosted LiveKit. Media is WebRTC over UDP straight to the server, so each participant sends one stream up regardless of room size.",
  },
  {
    icon: FiZap,
    title: "Realtime everywhere",
    body: "Every mutation publishes onto Redis streams and fans out over gRPC. Joining a channel mid-session starts delivering right away.",
  },
  {
    icon: FiLayers,
    title: "Many tabs, one account",
    body: "Sockets are tracked per connection rather than per user, so a second tab does not disconnect the first.",
  },
  {
    icon: FiShield,
    title: "Presence that self-heals",
    body: "The SFU owns the voice roster through signed webhooks, so a refresh, a crash or a closed laptop clears you from the channel.",
  },
];

export default function Features() {
  return (
    <section id="features" className="relative mx-auto max-w-6xl px-5 py-24 sm:px-8">
      <Reveal className="mx-auto max-w-2xl text-center">
        <h2 className="text-balance text-3xl font-bold text-white sm:text-4xl">
          What it does today
        </h2>
        <p className="mt-4 text-pretty text-ink-300">
          Most of the work sits behind the message list, in what reaches
          everyone else's screen when something changes.
        </p>
      </Reveal>

      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature, i) => (
          <Reveal key={feature.title} delay={([0, 70, 140] as const)[i % 3]}>
            <article className="group h-full rounded-2xl border border-white/[0.07] bg-white/[0.02] p-6 transition-all duration-300 hover:-translate-y-1 hover:border-rain-400/30 hover:bg-white/[0.04]">
              <div className="mb-5 inline-flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-rain-400/20 to-iris-400/10 text-rain-300 transition-colors group-hover:text-rain-200">
                <feature.icon size={19} />
              </div>
              <h3 className="text-[17px] font-semibold text-white">
                {feature.title}
              </h3>
              <p className="mt-2.5 text-sm leading-relaxed text-ink-300">
                {feature.body}
              </p>
            </article>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
