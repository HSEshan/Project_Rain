import { FiCheck, FiMic, FiPhoneOff, FiVolume2 } from "react-icons/fi";
import Reveal from "./Reveal";

const POINTS = [
  "One upstream per person, however many are listening",
  "Audio-only grant enforced server side, not just in the client",
  "Presence driven by signed webhooks, so a dropped connection clears itself",
  "TCP fallback for networks that block UDP",
];

const TILES = [
  { name: "eshan", color: "from-rain-400 to-iris-400", speaking: true },
  { name: "priya", color: "from-emerald-400 to-teal-500", speaking: false },
  { name: "sam", color: "from-amber-400 to-orange-500", speaking: true },
  { name: "júlia", color: "from-fuchsia-400 to-purple-500", speaking: false },
];

function Waveform({ active }: { active: boolean }) {
  return (
    <span className="flex h-4 items-end gap-[3px]" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className={`w-[3px] origin-bottom rounded-full ${
            active ? "h-4 bg-emerald-400 animate-equalize" : "h-1 bg-ink-600"
          }`}
          style={active ? { animationDelay: `${i * 120}ms` } : undefined}
        />
      ))}
    </span>
  );
}

export default function VoiceShowcase() {
  return (
    <section id="voice" className="mx-auto max-w-6xl px-5 py-24 sm:px-8">
      <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
        <Reveal>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-rain-300">
            Voice
          </p>
          <h2 className="mt-4 text-balance text-3xl font-bold text-white sm:text-4xl">
            Group voice on a self-hosted SFU
          </h2>
          <p className="mt-5 text-pretty leading-relaxed text-ink-300">
            Every participant sends one stream up and receives one per speaker,
            so the room does not get heavier for each person as it fills. Tested
            between two people in different states for two hours, with ICE
            selecting UDP in 39ms.
          </p>
          <ul className="mt-7 space-y-3">
            {POINTS.map((point) => (
              <li key={point} className="flex gap-3 text-sm text-ink-200">
                <FiCheck
                  className="mt-0.5 shrink-0 text-rain-300"
                  size={16}
                  aria-hidden
                />
                <span className="text-pretty">{point}</span>
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={140}>
          <div className="gradient-border rounded-2xl bg-ink-900/80 p-6 shadow-lift sm:p-8">
            <div className="mb-6 flex items-center gap-2">
              <FiVolume2 className="text-emerald-400" size={16} />
              <span className="text-sm font-medium text-white">
                general-voice
              </span>
              <span className="ml-auto font-mono text-[11px] text-ink-400">
                udp · 39ms
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {TILES.map((tile) => (
                <div
                  key={tile.name}
                  className={`flex flex-col items-center gap-2.5 rounded-xl border p-4 transition-colors ${
                    tile.speaking
                      ? "border-emerald-400/40 bg-emerald-400/[0.06]"
                      : "border-white/[0.07] bg-white/[0.02]"
                  }`}
                >
                  <span className="relative">
                    {tile.speaking && (
                      <span className="absolute inset-0 rounded-full ring-2 ring-emerald-400 animate-pulse-ring" />
                    )}
                    <span
                      className={`flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br text-base font-bold text-ink-950 ${tile.color}`}
                    >
                      {tile.name.charAt(0).toUpperCase()}
                    </span>
                  </span>
                  <span className="max-w-full truncate text-xs text-ink-200">
                    {tile.name}
                  </span>
                  <Waveform active={tile.speaking} />
                </div>
              ))}
            </div>

            <div className="mt-6 flex items-center justify-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-ink-100">
                <FiMic size={16} />
              </span>
              <span className="flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-ink-100">
                <FiVolume2 size={16} />
              </span>
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-red-500/90 text-white">
                <FiPhoneOff size={16} />
              </span>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
