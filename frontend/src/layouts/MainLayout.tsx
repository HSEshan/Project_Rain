import { Outlet } from "react-router-dom";
import { Sidebar } from "../sidebar/components/Sidebar";
import { WebSocketProvider } from "../providers/WebsocketProvider";

export default function MainLayout() {
  return (
    <WebSocketProvider>
      <div style={{ display: "flex", height: "100vh" }}>
        <Sidebar />
        <div style={{ flexGrow: 1, backgroundColor: "#313338" }}>
          <Outlet />
        </div>
      </div>
    </WebSocketProvider>
  );
}
