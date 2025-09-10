import { Link } from "react-router-dom";

export interface LinkButtonProps {
  to: string;
  className?: string;
  children: React.ReactNode;
  unread?: boolean;
  active?: boolean;
}

export default function LinkButton({
  to,
  className,
  children,
  unread,
  active,
}: LinkButtonProps) {
  return (
    <Link
      to={to}
      className={`w-full h-10 rounded-sm flex items-center justify-center ${className} ${
        active ? "bg-blue-500" : "bg-gray-700"
      }`}
    >
      {children}
      {unread && (
        <span className="relative top-[-10px] right-[-30px] w-3 h-3 bg-red-500 rounded-full" />
      )}
    </Link>
  );
}
