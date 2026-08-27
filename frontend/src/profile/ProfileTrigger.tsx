import { useProfileStore } from "./profileStore";

/**
 * Wraps anything that names a person and makes it open their card.
 *
 * A component rather than an `onClick` copied into six call sites, so that the
 * hover and focus treatment for "this is a person you can look at" is defined
 * once. Renders a plain button with no styling of its own beyond `display`, so
 * it never disturbs the layout it is dropped into.
 */
export default function ProfileTrigger({
  userId,
  className = "",
  label,
  children,
}: {
  userId?: string;
  className?: string;
  /** Screen-reader name, when the visible content is only an avatar. */
  label?: string;
  children: React.ReactNode;
}) {
  const openProfile = useProfileStore((state) => state.openProfile);

  // Without an id there is nothing to open, so render the content untouched
  // rather than a button that does nothing.
  if (!userId) return <>{children}</>;

  return (
    <button
      type="button"
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        void openProfile(userId);
      }}
      className={`cursor-pointer rounded-lg transition-opacity hover:opacity-80 focus-visible:opacity-80 ${className}`}
    >
      {children}
    </button>
  );
}
