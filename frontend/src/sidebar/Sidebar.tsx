import { useAuth } from "../auth/AuthContext";
import { useWebSocket } from "../utils/WebsocketProvider";
import SideBarButton from "./SideBarButton";
import logoutIcon from "../assets/logout_icon.svg";
import { PiUserCircle } from "react-icons/pi";
import { PiShield } from "react-icons/pi";
import { RiHome2Line } from "react-icons/ri";

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
      <SideBarButton to="/home" toolTipText="Home">
        <RiHome2Line size={30} />
      </SideBarButton>
      <SideBarButton to="/dm" toolTipText="Messages">
        <PiUserCircle size={30} />
      </SideBarButton>
      <SideBarButton to="/guild" toolTipText="Guilds">
        <PiShield size={30} />
      </SideBarButton>
      <SideBarButton onClick={logout} toolTipText="Logout">
        {<img src={logoutIcon} alt="Logout" />}
      </SideBarButton>
    </div>
  );
}
