import { Outlet, NavLink } from "react-router-dom";
import "./HomeLayout.css";

const items = [
  { path: ".", label: "Whats New" },
  { path: "./trending", label: "Trending" },
];

export default function HomeLayout() {
  return (
    <div style={{ padding: "1rem" }}>
      <h2>🏠 Home</h2>
      <div className="button-container">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={true}
            className={({ isActive }) =>
              `icon-button2 ${isActive ? "active" : ""}`
            }
            title={item.label}
          >
            {item.label[0]}
          </NavLink>
        ))}
      </div>
      <Outlet />
    </div>
  );
}
