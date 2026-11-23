import { useEffect, useRef } from "react";
import type { VideoTrack } from "livekit-client";
import { FiMicOff } from "react-icons/fi";
import { useUserStore } from "../shared/userStore";
import { useVoiceStore } from "./voiceStore";

/**
 * One camera, drawn into its own `<video>` element.
 *
 * The track is attached here rather than in the store because LiveKit's
 * adaptive streaming watches the element it is attached to: its size picks the
 * simulcast layer, and an element that is hidden or gone pauses the stream. An
 * element per tile is what makes a small tile cost a small stream.
 *
 * Our own camera is mirrored, the way every video app shows you to yourself;
 * everyone else sees it the right way round.
 */
export function VideoView({
  track,
  mirror = false,
  fit = "cover",
}: {
  track: VideoTrack;
  mirror?: boolean;
  fit?: "cover" | "contain";
}) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    track.attach(element);
    return () => {
      track.detach(element);
    };
  }, [track]);

  return (
    <video
      ref={ref}
      autoPlay
      playsInline
      // Video only: the audio is attached separately, and an unmuted element
      // with no audio track is what makes some browsers refuse to autoplay
      muted
      className={`h-full w-full bg-ink-900 ${fit === "cover" ? "object-cover" : "object-contain"} ${
        mirror ? "-scale-x-100" : ""
      }`}
    />
  );
}

/**
 * A person's camera with their name on it, for anywhere a call shows video.
 * The speaking ring is the tile's border, since there is no avatar to put it on.
 */
export function VideoTile({
  userId,
  track,
  isSelf,
  muted,
  className = "",
}: {
  userId: string;
  track: VideoTrack;
  isSelf: boolean;
  muted?: boolean;
  className?: string;
}) {
  const name = useUserStore((state) => state.users[userId]?.username) ?? "…";
  const speaking = useVoiceStore((state) => state.speaking[userId] ?? false);

  return (
    <div
      className={`relative aspect-video overflow-hidden rounded-2xl border-2 bg-ink-900 transition-colors ${
        speaking ? "border-emerald-400" : "border-white/[0.07]"
      } ${className}`}
    >
      <VideoView track={track} mirror={isSelf} />
      <span className="absolute bottom-2 left-2 flex max-w-[calc(100%-1rem)] items-center gap-1.5 rounded-lg bg-ink-950/70 px-2 py-1 text-xs text-ink-100 backdrop-blur-sm">
        <span className="truncate">{isSelf ? `${name} (you)` : name}</span>
        {muted && <FiMicOff size={12} className="shrink-0 text-red-400" />}
      </span>
    </div>
  );
}
