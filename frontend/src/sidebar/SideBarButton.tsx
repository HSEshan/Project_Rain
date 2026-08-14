import { Link } from "react-router-dom";
import Tooltip from "../shared/Tooltip";

export interface SideBarButtonProps {
  to?: string;
  children?: React.ReactNode;
  toolTipText?: string;
  onClick?: () => void;
  active?: boolean;
}

export default function SideBarButton({
  to,
  children,
  toolTipText,
  onClick,
  active,
}: SideBarButtonProps) {
  const className = `w-12 h-12 flex flex-col items-center justify-center rounded-xl cursor-pointer ${
    active ? "bg-gray-800 text-blue-500" : "bg-gray-700 text-white"
  }`;

  return (
    <Tooltip
      text={toolTipText || ""}
      position="right"
      speed={200}
      delay={0}
      className="w-12 h-12 flex flex-col items-center justify-center rounded-xl bg-gray-700"
      disabled={!toolTipText}
    >
      {/* Without a destination this is an action (logout), not navigation —
          rendering a Link to "" would also navigate to the current route. */}
      {to ? (
        <Link to={to} onClick={onClick} className={className}>
          {children}
        </Link>
      ) : (
        <button type="button" onClick={onClick} className={className}>
          {children}
        </button>
      )}
    </Tooltip>
  );
}
