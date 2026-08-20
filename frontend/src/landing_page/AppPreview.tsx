import { FiHash, FiMic, FiVolume2 } from "react-icons/fi";

/**
 * A still of the product, built in markup rather than a screenshot: it stays
 * sharp at any size, restyles itself with the design tokens, and never goes
 * stale against the real UI the way a PNG does.
 */

const CHANNELS = [
  { name: "general-text", active: true },
  { name: "deploys", active: false },
  { name: "design", active: false },
];

const MESSAGES = [
  {
    author: "priya",
    color: "from-emerald-400 to-teal-500",
    time: "20:14",
    lines: ["voice is up on the new box"],
  },
  {
    author: "eshan",
    color: "from-rain-400 to-iris-400",
    time: "20:14",
    lines: ["ICE picked udp in 39ms", "held for two hours, no drops"],
  },
  {
    author: "priya",
    color: "from-emerald-400 to-teal-500",
    time: "20:16",
    lines: ["nice. jumping in now"],
  },
];

const IN_VOICE = [
  { name: "eshan", color: "from-rain-400 to-iris-400", speaking: true },
  { name: "priya", color: "from-emerald-400 to-teal-500", speaking: false },
];

function Bars() {
  return (
    <span className="flex items-end gap-[2px]" aria-hidden>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-3 w-[3px] origin-bottom rounded-full bg-emerald-400 animate-equalize"
          style={{ animationDelay: `${i * 140}ms` }}
        />
      ))}
    </span>
  );
}

export default function AppPreview() {
  return (
    <div className="gradient-border overflow-hidden rounded-2xl bg-ink-900/90 shadow-lift ring-1 ring-white/5 backdrop-blur-xl">
      {/* Window chrome */}
      <div className="flex items-center gap-2 border-b border-white/[0.06] bg-ink-850/80 px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
        <span className="ml-3 truncate font-mono text-[11px] text-ink-400">
          rain / #general-text
        </span>
      </div>

      <div className="flex h-[336px] text-left sm:h-[380px]">
        {/* Channel rail — hidden on the narrowest screens so the chat keeps room */}
        <aside className="hidden w-44 shrink-0 flex-col gap-4 border-r border-white/[0.06] bg-ink-900/60 p-3 sm:flex">
          <p className="px-1 text-[10px] font-semibold uppercase tracking-widest text-ink-400">
            Text
          </p>
          <div className="-mt-2 space-y-0.5">
            {CHANNELS.map((c) => (
              <div
                key={c.name}
                className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13px] ${
                  c.active ? "bg-white/[0.07] text-white" : "text-ink-400"
                }`}
              >
                <FiHash size={13} className="shrink-0 opacity-70" />
                <span className="truncate">{c.name}</span>
              </div>
            ))}
          </div>

          <p className="px-1 text-[10px] font-semibold uppercase tracking-widest text-ink-400">
            Voice
          </p>
          <div className="-mt-2">
            <div className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13px] text-ink-200">
              <FiVolume2 size={13} className="shrink-0 text-emerald-400" />
              <span className="truncate">general-voice</span>
            </div>
            <div className="mt-1 space-y-1.5 pl-3">
              {IN_VOICE.map((u) => (
                <div key={u.name} className="flex items-center gap-2">
                  <span
                    className={`flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-br text-[9px] font-bold text-ink-950 ${u.color}`}
                  >
                    {u.name.charAt(0).toUpperCase()}
                  </span>
                  <span className="truncate text-[11px] text-ink-300">
                    {u.name}
                  </span>
                  {u.speaking && <Bars />}
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Conversation */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-2.5">
            <FiHash size={14} className="text-ink-400" />
            <span className="text-[13px] font-medium text-white">
              general-text
            </span>
            <span className="ml-auto flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              live
            </span>
          </div>

          <div className="flex-1 space-y-3.5 overflow-hidden p-4">
            {MESSAGES.map((m, i) => (
              <div key={i} className="flex gap-2.5">
                <span
                  className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br text-[11px] font-bold text-ink-950 ${m.color}`}
                >
                  {m.author.charAt(0).toUpperCase()}
                </span>
                <div className="min-w-0">
                  <p className="flex items-baseline gap-2">
                    <span className="text-[13px] font-semibold text-white">
                      {m.author}
                    </span>
                    <span className="font-mono text-[10px] text-ink-500">
                      {m.time}
                    </span>
                  </p>
                  {m.lines.map((line) => (
                    <p
                      key={line}
                      className="text-[13px] leading-relaxed text-ink-200"
                    >
                      {line}
                    </p>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="p-3">
            <div className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-ink-850/70 px-3 py-2.5">
              <span className="flex-1 truncate text-[13px] text-ink-500">
                Message #general-text
              </span>
              <FiMic size={14} className="text-ink-500" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
