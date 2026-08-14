export default function EmptyState({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center px-6">
      <p className="text-lg text-gray-300">{title}</p>
      {hint && <p className="text-sm text-gray-500">{hint}</p>}
    </div>
  );
}
