import { Link } from "react-router-dom";

export interface SideBarButtonProps {
  to?: string;
  onClick?: () => void;
  children: React.ReactNode;
}

export default function SideBarButton({
  to,
  onClick,
  children,
}: SideBarButtonProps) {
  return (
    <Link
      to={to ?? ""}
      onClick={onClick}
      className={`w-12 h-12 flex flex-col items-center justify-center rounded-xl bg-gray-700 ${
        to ? "" : "cursor-pointer"
      }`}
    >
      {children}
    </Link>
  );
}
