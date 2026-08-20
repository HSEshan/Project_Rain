import { forwardRef } from "react";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  icon?: React.ReactNode;
}

const FIELD =
  "w-full rounded-xl border bg-ink-850/80 px-3.5 text-[15px] text-white placeholder-ink-400 transition-colors focus:outline-none focus:ring-2 focus:ring-rain-400/60 focus:border-rain-400/40";

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, icon, className = "", id, ...props },
  ref
) {
  const inputId = id ?? props.name;
  return (
    <div className="space-y-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-xs font-medium uppercase tracking-wide text-ink-300"
        >
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-400">
            {icon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`${FIELD} h-11 ${icon ? "pl-10" : ""} ${
            error ? "border-red-500/50" : "border-white/10"
          } ${className}`}
          {...props}
        />
      </div>
      {error ? (
        <p className="text-xs text-red-400">{error}</p>
      ) : (
        hint && <p className="text-xs text-ink-400">{hint}</p>
      )}
    </div>
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string }
>(function Textarea({ label, className = "", id, ...props }, ref) {
  const areaId = id ?? props.name;
  return (
    <div className="space-y-1.5">
      {label && (
        <label
          htmlFor={areaId}
          className="block text-xs font-medium uppercase tracking-wide text-ink-300"
        >
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={areaId}
        className={`${FIELD} resize-none border-white/10 py-2.5 ${className}`}
        {...props}
      />
    </div>
  );
});
