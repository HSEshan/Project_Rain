import { useState } from "react";
import { Link } from "react-router-dom";

export interface SideBarButtonProps {
  to?: string;
  children?: React.ReactNode;
  toolTipText?: string;
  onClick?: () => void;
}

export default function SideBarButton({
  to,
  children,
  toolTipText,
  onClick,
}: SideBarButtonProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div className="relative group">
      <Link
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        to={to ?? ""}
        onClick={onClick}
        className={`w-12 h-12 flex flex-col items-center justify-center rounded-xl bg-gray-700 ${
          to ? "" : "cursor-pointer"
        }`}
      >
        {children}
      </Link>

      {isHovered && toolTipText && (
        <div className="absolute left-full top-1/2 transform -translate-y-1/2 ml-2 px-2 py-1 bg-gray-700 text-white text-sm rounded-md shadow-lg whitespace-nowrap z-50">
          {toolTipText}
          {/* Tooltip arrow */}
          <div className="absolute right-full top-1/2 transform -translate-y-1/2 w-0 h-0 border-t-4 border-b-4 border-r-4 border-transparent border-r-gray-700"></div>
        </div>
      )}
    </div>
  );
}
