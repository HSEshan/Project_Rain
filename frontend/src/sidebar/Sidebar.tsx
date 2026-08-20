import { useLocation, useNavigate } from "react-router-dom";
import { FiHome, FiLogOut, FiMessageCircle, FiUsers } from "react-icons/fi";
import { useAuth } from "../auth/AuthContext";
import { useWebSocket } from "../utils/WebsocketProvider";
import { useGuildStore } from "../guild/guildStore";
import { useFriendStore } from "../friends/friendStore";
import { resetAllStores } from "../shared/resetStores";
import Avatar from "../shared/Avatar";
import ConnectionDot from "../shared/ConnectionDot";
import Logo from "../landing_page/Logo";
import SideBarButton from "./SideBarButton";

/**
 * Primary navigation. A vertical rail from `lg` up, a bottom bar below it —
 * on a phone, thumb reach beats a left edge.
 */
export function Sidebar() {
  const { disconnect } = useWebSocket();
  const { logout, getCurrentUser } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const invites = useGuildStore((state) => state.invites);
  const friendRequests = useFriendStore((state) => state.friendRequests);
  const user = getCurrentUser();

  const handleLogout = () => {
    disconnect();
    resetAllStores();
    logout();
    navigate("/login", { replace: true });
  };

  const destinations = [
    {
      to: "/home",
      label: "Home",
      icon: <FiHome size={19} />,
      active: location.pathname.startsWith("/home"),
      badge: 0,
    },
    {
      to: "/dm",
      label: "Messages",
      icon: <FiMessageCircle size={19} />,
      active: location.pathname.startsWith("/dm"),
      badge: friendRequests.length,
    },
    {
      to: "/guild",
      label: "Guilds",
      icon: <FiUsers size={19} />,
      active: location.pathname.startsWith("/guild"),
      badge: invites.length,
    },
  ];

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-40 flex h-16 shrink-0 items-center justify-around border-t border-white/[0.06] bg-ink-900/95 px-2 backdrop-blur-xl lg:static lg:h-auto lg:w-[68px] lg:flex-col lg:justify-start lg:gap-2 lg:border-r lg:border-t-0 lg:py-4"
    >
      <div className="hidden lg:mb-2 lg:block">
        <Logo size={26} withText={false} />
      </div>

      {destinations.map((destination) => (
        <SideBarButton
          key={destination.to}
          to={destination.to}
          label={destination.label}
          active={destination.active}
          badge={destination.badge}
        >
          {destination.icon}
        </SideBarButton>
      ))}

      {/* Account block: rail foot on desktop, one more bottom-bar slot on mobile.
          Rendered twice rather than once with responsive classes because the
          two layouts want different children, not a different arrangement. */}
      <div className="hidden lg:mt-auto lg:flex lg:flex-col lg:items-center lg:gap-3">
        <ConnectionDot />
        <Avatar name={user?.username} seed={user?.id} size="sm" />
        <SideBarButton label="Log out" onClick={handleLogout} destructive>
          <FiLogOut size={18} />
        </SideBarButton>
      </div>

      <span className="lg:hidden">
        <SideBarButton label="Log out" onClick={handleLogout} destructive>
          <FiLogOut size={19} />
        </SideBarButton>
      </span>
    </nav>
  );
}
