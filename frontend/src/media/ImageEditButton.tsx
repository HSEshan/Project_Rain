import { useRef, useState } from "react";
import { FiCamera } from "react-icons/fi";
import Spinner from "../shared/Spinner";
import { errorText } from "../shared/errors";
import { ACCEPTED_IMAGE_TYPES, preflightError } from "./apiClient";

/**
 * An avatar you can click to replace. Wraps whatever circle it is given.
 *
 * One component for the two places an image is owned by a single editor (your
 * avatar on your own card, a guild's icon for its admins), so the hover
 * affordance, the busy state and the error wording are defined once.
 *
 * The camera badge is always visible, not only on hover: on a phone there is
 * no hover, and an avatar that is secretly a button is one nobody finds.
 * Failures are handed to `onError` rather than rendered here, because the two
 * callers have room for a message in very different places.
 */
export default function ImageEditButton({
  children,
  label,
  onUpload,
  onError,
  badgeSize = "md",
}: {
  children: React.ReactNode;
  /** Screen-reader name, e.g. "Change your avatar". */
  label: string;
  onUpload: (file: File) => Promise<unknown>;
  onError: (message: string) => void;
  badgeSize?: "sm" | "md";
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const handleFile = async (file: File | undefined) => {
    // Reset so choosing the same file twice (after a failure) fires again
    if (input.current) input.current.value = "";
    if (!file) return;

    const refused = preflightError(file);
    if (refused) {
      onError(refused);
      return;
    }

    setBusy(true);
    onError("");
    try {
      await onUpload(file);
    } catch (error) {
      onError(errorText(error, "Could not upload that image."));
    } finally {
      setBusy(false);
    }
  };

  const badge = badgeSize === "sm" ? "h-4 w-4 -bottom-0.5 -right-0.5" : "h-7 w-7 bottom-0 right-0";

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={busy}
      onClick={() => input.current?.click()}
      className="group relative shrink-0 rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rain-400/60"
    >
      <span className="block transition-opacity group-hover:opacity-80">{children}</span>
      {busy && (
        <span className="absolute inset-0 flex items-center justify-center rounded-full bg-ink-950/60">
          <Spinner />
        </span>
      )}
      <span
        className={`absolute flex items-center justify-center rounded-full border-2 border-ink-850 bg-rain-400 text-ink-950 ${badge}`}
      >
        <FiCamera size={badgeSize === "sm" ? 8 : 13} />
      </span>
      <input
        ref={input}
        type="file"
        accept={ACCEPTED_IMAGE_TYPES}
        className="hidden"
        onChange={(event) => void handleFile(event.target.files?.[0])}
      />
    </button>
  );
}
