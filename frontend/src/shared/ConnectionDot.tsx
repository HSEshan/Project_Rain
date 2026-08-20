import { useWebSocket } from "../utils/WebsocketProvider";

/**
 * Realtime socket state. The only always-visible signal that events are
 * actually flowing — a chat app that has silently stopped receiving looks
 * exactly like a quiet one.
 */
export default function ConnectionDot({
  withLabel = false,
  className = "",
}: {
  withLabel?: boolean;
  className?: string;
}) {
  const { isConnected } = useWebSocket();

  return (
    <span
      className={`inline-flex items-center gap-1.5 ${className}`}
      title={isConnected ? "Connected" : "Reconnecting…"}
    >
      <span
        className={`h-2 w-2 rounded-full transition-colors ${
          isConnected
            ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
            : "animate-pulse bg-amber-400"
        }`}
      />
      {withLabel && (
        <span className="text-xs text-ink-400">
          {isConnected ? "Live" : "Reconnecting"}
        </span>
      )}
    </span>
  );
}
