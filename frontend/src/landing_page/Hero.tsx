import { FiArrowRight, FiGithub } from "react-icons/fi";
import { Button } from "../shared/Button";
import Aurora from "./Aurora";
import AppPreview from "./AppPreview";
import TechStack from "./TechStack";

const STATS = [
  { value: "39ms", label: "ICE to first audio" },
  { value: "9", label: "services in the stack" },
  { value: "16", label: "Redis stream shards" },
  { value: "79", label: "end-to-end checks" },
];

export default function Hero() {
  return (
    <section className="relative overflow-hidden pt-16">
      {/* WebGL aurora, pinned behind everything and pointer-transparent */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[620px] opacity-70">
        <Aurora amplitude={1.1} blend={0.6} speed={0.6} />
      </div>
      {/* Fade the aurora into the page rather than ending it on a hard edge */}
      <div className="pointer-events-none absolute inset-x-0 top-[420px] h-56 bg-gradient-to-b from-transparent to-ink-950" />

      <div className="relative mx-auto max-w-6xl px-5 pb-20 pt-16 sm:px-8 sm:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <span className="inline-flex animate-fade-up items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3.5 py-1.5 text-xs text-ink-200 backdrop-blur">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </span>
            Self-hosted, running in production
          </span>

          <h1 className="mt-7 animate-fade-up text-balance text-[2.6rem] font-bold leading-[1.05] text-white delay-70 sm:text-6xl lg:text-7xl">
            Real-time chat and voice,{" "}
            <span className="gradient-text">self-hosted.</span>
          </h1>

          <p className="mx-auto mt-6 max-w-xl animate-fade-up text-pretty text-base leading-relaxed text-ink-300 delay-140 sm:text-lg">
            Rain is a Discord-style platform with direct messages, guild
            channels, and group voice running on a self-hosted SFU. Built as a
            portfolio project to work through realtime architecture end to end.
          </p>

          <div className="mt-9 flex animate-fade-up flex-col items-center justify-center gap-3 delay-210 sm:flex-row">
            <Button to="/login" variant="primary" size="lg" icon={<FiArrowRight />}>
              Start talking
            </Button>
            <Button
              variant="secondary"
              size="lg"
              icon={<FiGithub />}
              onClick={() =>
                document
                  .getElementById("architecture")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
            >
              See how it works
            </Button>
          </div>
        </div>

        <div className="mt-12 animate-fade-up delay-280 sm:mt-14">
          <TechStack />
        </div>

        <div className="mt-10 animate-fade-up delay-280 sm:mt-12">
          <AppPreview />
        </div>

        <dl className="mt-14 grid animate-fade-up grid-cols-2 gap-x-6 gap-y-8 delay-350 sm:mt-16 lg:grid-cols-4">
          {STATS.map((stat) => (
            <div key={stat.label} className="text-center">
              <dt className="gradient-text text-3xl font-bold sm:text-4xl">
                {stat.value}
              </dt>
              <dd className="mt-1.5 text-xs text-ink-400 sm:text-sm">
                {stat.label}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
