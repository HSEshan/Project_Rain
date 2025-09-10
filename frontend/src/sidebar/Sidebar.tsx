import { useAuth } from "../auth/AuthContext";
import { useWebSocket } from "../utils/WebsocketProvider";
import SideBarButton from "./SideBarButton";
import logoutIcon from "../assets/logout_icon.svg";

export function Sidebar() {
  const { isConnected } = useWebSocket();
  const { logout } = useAuth();

  return (
    <div className="w-20 bg-gray-900 text-white flex flex-col items-center py-4 gap-4">
      {isConnected ? (
        <div className="w-3 h-3 bg-green-500 rounded-full" />
      ) : (
        <div className="w-3 h-3 bg-red-500 rounded-full" />
      )}
      <SideBarButton to="/dm">DM</SideBarButton>
      <SideBarButton to="/guild">Guild</SideBarButton>
      <SideBarButton onClick={logout}>
        {<img src={logoutIcon} alt="Logout" />}
      </SideBarButton>
    </div>
  );
}
