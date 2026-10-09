import type { Attachment } from "../shared/types";

/** Longest side an image is drawn at in the chat, in CSS pixels. */
const MAX_DISPLAY = 320;

/**
 * The images on one message.
 *
 * **Every image reserves its space before it loads.** The server stores each
 * image's dimensions, and the box is sized from them, so a picture arriving
 * does not push the conversation down. That matters more than it looks: the
 * message list scrolls to the bottom on new messages, and an image that grows
 * after the scroll leaves you looking at the middle of it.
 *
 * One image keeps its own shape; several become a grid of squares, which is
 * what every chat app does, because four differently shaped pictures side by
 * side never line up. Each opens full size in a new tab.
 */
export default function AttachmentGallery({
  attachments,
}: {
  attachments: Attachment[];
}) {
  if (attachments.length === 0) return null;

  if (attachments.length === 1) {
    const [image] = attachments;
    const scale = Math.min(1, MAX_DISPLAY / image.width, MAX_DISPLAY / image.height);
    return (
      <div className="mt-1.5">
        <ImageLink image={image}>
          <img
            src={image.url}
            alt=""
            loading="lazy"
            decoding="async"
            width={Math.round(image.width * scale)}
            height={Math.round(image.height * scale)}
            style={{ aspectRatio: `${image.width} / ${image.height}` }}
            className="block h-auto max-w-full rounded-xl border border-white/[0.07] bg-ink-850"
          />
        </ImageLink>
      </div>
    );
  }

  return (
    <div className="mt-1.5 grid max-w-sm grid-cols-2 gap-1.5">
      {attachments.map((image) => (
        <ImageLink key={image.id} image={image} fill>
          <img
            src={image.url}
            alt=""
            loading="lazy"
            decoding="async"
            className="block aspect-square w-full rounded-xl border border-white/[0.07] bg-ink-850 object-cover"
          />
        </ImageLink>
      ))}
    </div>
  );
}

function ImageLink({
  image,
  fill = false,
  children,
}: {
  image: Attachment;
  /** Fill a grid cell rather than shrink to the image. */
  fill?: boolean;
  children: React.ReactNode;
}) {
  return (
    <a
      href={image.url}
      target="_blank"
      rel="noreferrer noopener"
      aria-label={`Open image, ${image.width} by ${image.height}`}
      className={`block max-w-full rounded-xl transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rain-400/60 ${
        fill ? "w-full" : "w-fit"
      }`}
    >
      {children}
    </a>
  );
}
