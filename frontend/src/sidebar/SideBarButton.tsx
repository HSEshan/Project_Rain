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
  return (
    <Tooltip
      text={toolTipText || ""}
      position="right"
      speed={200}
      delay={0}
      className="w-12 h-12 flex flex-col items-center justify-center rounded-xl bg-gray-700"
      disabled={!toolTipText}
    >
      <Link
        to={to ?? ""}
        onClick={onClick}
        className={`w-12 h-12 flex flex-col items-center justify-center rounded-xl bg-gray-700 ${
          to ? "" : "cursor-pointer"
        } ${active ? "bg-gray-800 text-blue-500" : "bg-gray-700 text-white"}`}
      >
        {children}
      </Link>
    </Tooltip>
  );
}
