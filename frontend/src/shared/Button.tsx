import { forwardRef } from "react";
import { Link } from "react-router-dom";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "subtle";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  // The sheen element lives inside the button, so only this variant pays for it
  primary:
    "relative overflow-hidden bg-gradient-to-r from-rain-400 to-iris-400 text-ink-950 font-semibold shadow-glow hover:brightness-110 active:brightness-95",
  secondary:
    "bg-white/[0.06] text-ink-100 border border-white/10 hover:bg-white/[0.1] hover:border-white/20",
  ghost: "text-ink-300 hover:text-white hover:bg-white/[0.06]",
  subtle: "bg-ink-800 text-ink-100 hover:bg-ink-700 border border-white/5",
  danger:
    "bg-red-500/15 text-red-300 border border-red-500/30 hover:bg-red-500/25 hover:text-red-200",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-xl",
  lg: "h-12 px-6 text-[15px] gap-2.5 rounded-xl",
};

const BASE =
  "inline-flex items-center justify-center whitespace-nowrap font-medium transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none select-none";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /** Renders a react-router Link styled as a button. */
  to?: string;
  loading?: boolean;
  icon?: React.ReactNode;
  full?: boolean;
}

/**
 * The one button in the app. Every other component styles itself through this
 * so hover, focus, disabled and loading behave identically everywhere.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = "secondary",
      size = "md",
      to,
      loading,
      icon,
      full,
      className = "",
      children,
      disabled,
      ...props
    },
    ref
  ) {
    const classes = `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${
      full ? "w-full" : ""
    } ${className}`;

    const inner = (
      <>
        {variant === "primary" && (
          <span
            aria-hidden
            className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 skew-x-[-20deg] bg-white/25 blur-md animate-sheen"
          />
        )}
        {loading ? (
          <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent" />
        ) : (
          icon
        )}
        <span className="relative">{children}</span>
      </>
    );

    if (to) {
      return (
        <Link to={to} className={classes}>
          {inner}
        </Link>
      );
    }

    return (
      <button
        ref={ref}
        className={classes}
        disabled={disabled || loading}
        {...props}
      >
        {inner}
      </button>
    );
  }
);
