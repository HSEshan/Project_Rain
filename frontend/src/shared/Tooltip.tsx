import { useState, type ReactNode, useRef, useEffect } from "react";

export type TooltipPosition =
  | "top"
  | "bottom"
  | "left"
  | "right"
  | "top-left"
  | "top-right"
  | "bottom-left"
  | "bottom-right";

export interface TooltipProps {
  text: string;
  children: ReactNode;
  position?: TooltipPosition;
  speed?: number; // Duration in milliseconds
  delay?: number; // Delay in milliseconds before showing tooltip
  className?: string;
  disabled?: boolean;
}

export default function Tooltip({
  text,
  children,
  position = "right",
  speed = 300,
  delay = 0,
  className = "",
  disabled = false,
}: TooltipProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isHovered) {
      if (delay > 0) {
        timeoutRef.current = setTimeout(() => setShowTooltip(true), delay);
      } else {
        setShowTooltip(true);
      }
    } else {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      setShowTooltip(false);
    }

    // Cleanup timeout on unmount
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [isHovered, delay]);

  if (disabled || !text) {
    return <>{children}</>;
  }

  const getPositionClasses = () => {
    const baseClasses =
      "absolute px-2 py-1 bg-gray-700 text-white text-sm rounded-md shadow-lg whitespace-nowrap z-50";

    switch (position) {
      case "top":
        return `${baseClasses} bottom-full left-1/2 transform -translate-x-1/2 mb-2 origin-bottom`;
      case "bottom":
        return `${baseClasses} top-full left-1/2 transform -translate-x-1/2 mt-2 origin-top`;
      case "left":
        return `${baseClasses} right-full top-1/2 transform -translate-y-1/2 mr-2 origin-right`;
      case "right":
        return `${baseClasses} left-full top-1/2 transform -translate-y-1/2 ml-2 origin-left`;
      case "top-left":
        return `${baseClasses} bottom-full left-0 mb-2 origin-bottom-left`;
      case "top-right":
        return `${baseClasses} bottom-full right-0 mb-2 origin-bottom-right`;
      case "bottom-left":
        return `${baseClasses} top-full left-0 mt-2 origin-top-left`;
      case "bottom-right":
        return `${baseClasses} top-full right-0 mt-2 origin-top-right`;
      default:
        return `${baseClasses} left-full top-1/2 transform -translate-y-1/2 ml-2 origin-left`;
    }
  };

  const getArrowClasses = () => {
    const baseArrowClasses = "absolute w-0 h-0";

    switch (position) {
      case "top":
        return `${baseArrowClasses} top-full left-1/2 transform -translate-x-1/2 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-700`;
      case "bottom":
        return `${baseArrowClasses} bottom-full left-1/2 transform -translate-x-1/2 border-l-4 border-r-4 border-b-4 border-transparent border-b-gray-700`;
      case "left":
        return `${baseArrowClasses} left-full top-1/2 transform -translate-y-1/2 border-t-4 border-b-4 border-l-4 border-transparent border-l-gray-700`;
      case "right":
        return `${baseArrowClasses} right-full top-1/2 transform -translate-y-1/2 border-t-4 border-b-4 border-r-4 border-transparent border-r-gray-700`;
      case "top-left":
        return `${baseArrowClasses} top-full left-2 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-700`;
      case "top-right":
        return `${baseArrowClasses} top-full right-2 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-700`;
      case "bottom-left":
        return `${baseArrowClasses} bottom-full left-2 border-l-4 border-r-4 border-b-4 border-transparent border-b-gray-700`;
      case "bottom-right":
        return `${baseArrowClasses} bottom-full right-2 border-l-4 border-r-4 border-b-4 border-transparent border-b-gray-700`;
      default:
        return `${baseArrowClasses} right-full top-1/2 transform -translate-y-1/2 border-t-4 border-b-4 border-r-4 border-transparent border-r-gray-700`;
    }
  };

  return (
    <div className="relative group">
      <div
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={className}
      >
        {children}
      </div>

      <div
        className={`${getPositionClasses()} transition-all ease-out ${
          showTooltip ? "scale-100 opacity-100" : "scale-0 opacity-0"
        }`}
        style={{ transitionDuration: `${speed}ms` }}
      >
        {text}
        <div className={getArrowClasses()}></div>
      </div>
    </div>
  );
}
