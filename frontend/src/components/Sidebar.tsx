import { NavLink } from "react-router-dom";

const icons = [
  { path: "/home", label: "Home" },
  { path: "/friends", label: "Friends" },
  { path: "/settings", label: "Settings" },
];

export default function Sidebar() {
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
    </div>
  );
}
