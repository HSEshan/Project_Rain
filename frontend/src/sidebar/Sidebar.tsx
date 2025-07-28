import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import logout_icon from "../assets/logout_icon.svg";

const icons = [
  { path: "/home", label: "Home" },
  { path: "/friends", label: "Friends" },
  { path: "/settings", label: "Settings" },
];

export default function Sidebar() {
  const { logout } = useAuth();

  return (
    <div className="w-[70px] bg-[#2b2d31] flex flex-col items-center pt-4 gap-4">
      {icons.map((icon) => (
        <NavLink
          key={icon.path}
          to={icon.path}
          className={({ isActive }) =>
            [
              "w-[45px] h-[45px] rounded-full flex items-center justify-center font-bold text-white",
              "bg-[#3c3f45] hover:bg-indigo-400 transition-colors duration-300",
              isActive && "bg-[#5865f2]",
            ]
              .filter(Boolean)
              .join(" ")
          }
          title={icon.label}
        >
          {icon.label[0]}
        </NavLink>
      ))}
      {/* Logout button */}
      <NavLink
        to="/auth"
        onClick={() => logout()}
        className="mt-5 w-[45px] h-[45px] rounded-full flex items-center justify-center font-bold text-white bg-[#3c3f45] hover:bg-indigo-400 transition-colors duration-300"
      >
        <img src={logout_icon} alt="logout" className="w-[20px] h-[20px]" />
      </NavLink>
    </div>
  );
}
