import { useEffect, useRef, useState } from "react";
import { FiSliders } from "react-icons/fi";
import { useUserStore } from "../shared/userStore";
import { useVoiceStore } from "./voiceStore";

/**
 * Output volume, master and per person, in one popover.
 *
 * One panel rather than a slider per participant tile, for two reasons. A DM
 * call has no tiles at all — it is a strip above the composer — and putting the
 * control in only one of the two places would mean the person who is too loud
 * is adjustable in a guild channel and not in a call. And a slider that lives
 * inside a hover state is a slider people discover by accident.
 *
 * Everything here is local. Volume is a fact about your speakers and the room
 * you are sitting in, so nothing is sent to the server and nobody else is told:
 * turning someone down is not muting them, and they should not find out.
 *
 * **It renders nothing when there is nobody to hear.** A volume control sitting
 * among your own mute and deafen buttons while you are alone in a channel reads
 * as a setting that applies to *you*, which is not what it does and is not a
 * thing that would make sense; and there is nothing for it to turn up or down
 * either. It appears when someone is audible and goes away when they leave.
 *
 * The icon is a slider rather than a speaker on purpose: deafen already owns
 * the speaker glyph, and two buttons side by side showing the same picture is
 * how you get a person muting themselves when they meant to turn someone down.
 */
export default function VolumeControl({ compact = false }: { compact?: boolean }) {
  const {
    audible,
    outputVolume,
    userVolumes,
    setOutputVolume,
    setUserVolume,
  } = useVoiceStore();
  const users = useUserStore((state) => state.users);
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const size = compact ? "h-9 w-9" : "h-12 w-12";
  const icon = compact ? 15 : 17;

  // Nothing audible, nothing to adjust. Hooks run first so this stays a valid
  // early return.
  if (audible.length === 0) return null;

  return (
    <div ref={container} className="relative">
      <button
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        title="Volume"
        aria-label="Volume"
        aria-expanded={open}
        className={`flex ${size} items-center justify-center rounded-full transition-all duration-200 ${
          open
            ? "bg-white/[0.16] text-white"
            : "bg-white/[0.08] text-ink-100 hover:bg-white/[0.14]"
        }`}
      >
        <FiSliders size={icon} />
      </button>

      {open && (
        <div
          // `bg-ink-850/95` on top of `glass`, the same way `Modal` does it. The
          // glass surface alone is 3% white and reads beautifully over a page
          // and not at all over a participant tile, which is exactly what this
          // opens on top of.
          // Anchored to the button's right edge, not centred on it. Centred
          // was the first attempt and half the panel fell off the right of the
          // viewport in the call bar, where this button sits a few pixels from
          // the edge of the screen. Opening leftwards fits in both bars and on
          // a phone.
          className="glass absolute bottom-full right-0 z-30 mb-3 w-64 rounded-2xl border-white/10 bg-ink-850/95 p-3.5 shadow-lift animate-scale-in"
          role="dialog"
          aria-label="Volume"
        >
          <VolumeSlider
            label="Output"
            value={outputVolume}
            onChange={setOutputVolume}
          />

          <div className="mt-3 space-y-3 border-t border-white/[0.07] pt-3">
            {audible.map((userId) => (
              <VolumeSlider
                key={userId}
                label={users[userId]?.username ?? "…"}
                // Nobody has turned this person up or down yet, and full is the
                // only sensible default for that.
                value={userVolumes[userId] ?? 1}
                onChange={(value) => setUserVolume(userId, value)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function VolumeSlider({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const percent = Math.round(value * 100);

  return (
    <label className="block">
      <span className="mb-1 flex items-center justify-between gap-2 text-[11px]">
        <span className="truncate text-ink-300">{label}</span>
        <span className="shrink-0 tabular-nums text-ink-500">{percent}%</span>
      </span>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={percent}
        // The slider speaks in percent because that is what the label shows;
        // the store speaks in 0 to 1 because that is what `element.volume`
        // takes. One conversion, here, rather than two units in the store.
        onChange={(event) => onChange(Number(event.target.value) / 100)}
        aria-label={`${label} volume`}
        className="slider"
      />
    </label>
  );
}
