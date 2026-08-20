/** Wordmark + droplet. Used by the landing nav, the auth page and the app rail. */
export default function Logo({
  size = 28,
  withText = true,
  className = "",
}: {
  size?: number;
  withText?: boolean;
  className?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden
        className="shrink-0"
      >
        <defs>
          <linearGradient id="rain-mark" x1="0" y1="0" x2="32" y2="32">
            <stop stopColor="#67E8F9" />
            <stop offset="0.55" stopColor="#22D3EE" />
            <stop offset="1" stopColor="#818CF8" />
          </linearGradient>
        </defs>
        {/* A droplet, drawn as a rotated square with three rounded corners */}
        <path
          d="M16 3.5c4.6 4.3 9.5 8.7 9.5 14.1A9.5 9.5 0 0 1 16 27.1a9.5 9.5 0 0 1-9.5-9.5C6.5 12.2 11.4 7.8 16 3.5Z"
          fill="url(#rain-mark)"
        />
        <circle cx="12.6" cy="19.4" r="2.6" fill="#04060C" fillOpacity="0.35" />
      </svg>
      {withText && (
        <span className="text-[19px] font-semibold tracking-tight text-white">
          Rain
        </span>
      )}
    </span>
  );
}
