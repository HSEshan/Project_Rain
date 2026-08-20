export default function EmptyState({
  title,
  hint,
  icon,
  action,
}: {
  title: string;
  hint?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      {icon && (
        <div className="mb-1 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-ink-300">
          {icon}
        </div>
      )}
      <p className="text-lg font-medium text-ink-100">{title}</p>
      {hint && <p className="max-w-sm text-sm text-ink-400 text-pretty">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
