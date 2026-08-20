import { FiArrowRight, FiCornerDownRight } from "react-icons/fi";
import Reveal from "./Reveal";

const PIPELINE = [
  {
    step: "01",
    title: "Ingress",
    detail: "Caddy to ws_gateway",
    body: "One socket per tab, authenticated by JWT on the query string.",
  },
  {
    step: "02",
    title: "Persist and publish",
    detail: "Postgres, XADD",
    body: "The message is stored, then written to one of 16 Redis stream shards.",
  },
  {
    step: "03",
    title: "Lease the shards",
    detail: "lease_manager",
    body: "Heartbeats assign every shard to exactly one live consumer.",
  },
  {
    step: "04",
    title: "Fan out",
    detail: "event_consumer, gRPC",
    body: "Consumers read their shards and route by whether the event addresses a user or a channel.",
  },
  {
    step: "05",
    title: "Deliver",
    detail: "ws_gateway to browser",
    body: "The gateway holding that socket pushes the frame. Membership changes re-register live.",
  },
];

export default function Architecture() {
  return (
    <section
      id="architecture"
      className="relative border-y border-white/[0.06] bg-ink-900/40 py-24"
    >
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-rain-300">
            Architecture
          </p>
          <h2 className="mt-4 text-balance text-3xl font-bold text-white sm:text-4xl">
            How a message reaches everyone else
          </h2>
          <p className="mt-4 text-pretty text-ink-300">
            Chat, presence and membership all travel the same event bus, so a
            second gateway instance is a deployment change rather than a
            rewrite.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-3 lg:grid-cols-5">
          {PIPELINE.map((stage, i) => (
            <Reveal
              key={stage.step}
              delay={([0, 70, 140, 210, 280] as const)[i]}
              className="h-full"
            >
              <div className="relative flex h-full flex-col rounded-2xl border border-white/[0.07] bg-ink-850/60 p-5">
                <span className="font-mono text-[11px] text-rain-300/80">
                  {stage.step}
                </span>
                <h3 className="mt-2 text-[15px] font-semibold text-white">
                  {stage.title}
                </h3>
                <p className="mt-1 font-mono text-[11px] text-ink-400">
                  {stage.detail}
                </p>
                <p className="mt-3 text-[13px] leading-relaxed text-ink-300">
                  {stage.body}
                </p>
                {/* Connector: horizontal on wide screens, vertical when stacked */}
                {i < PIPELINE.length - 1 && (
                  <>
                    <FiArrowRight
                      className="absolute -right-3 top-1/2 hidden -translate-y-1/2 text-ink-500 lg:block"
                      size={14}
                    />
                    <FiCornerDownRight
                      className="absolute -bottom-3 left-6 text-ink-500 lg:hidden"
                      size={14}
                    />
                  </>
                )}
              </div>
            </Reveal>
          ))}
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Reveal>
            <div className="h-full rounded-2xl border border-white/[0.07] bg-white/[0.02] p-6">
              <h3 className="text-[15px] font-semibold text-white">
                What travels the bus
              </h3>
              <p className="mt-2.5 text-sm leading-relaxed text-ink-300">
                Messages, friend requests, guild invites, membership changes and
                voice presence. All of it shares one event schema, with a single
                rule deciding whether an id refers to a user or a channel.
              </p>
            </div>
          </Reveal>
          <Reveal delay={70}>
            <div className="gradient-border h-full rounded-2xl bg-gradient-to-br from-rain-400/[0.07] to-transparent p-6">
              <h3 className="text-[15px] font-semibold text-white">
                What does not
              </h3>
              <p className="mt-2.5 text-sm leading-relaxed text-ink-300">
                Audio. Media is WebRTC over UDP between the browser and the SFU,
                so it never touches Redis or gRPC. The two paths are kept
                separate on purpose, and each one scales on its own terms.
              </p>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
