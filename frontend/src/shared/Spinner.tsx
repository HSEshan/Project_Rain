export default function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-2 border-rain-400/30 border-t-rain-400 ${className}`}
    />
  );
}
