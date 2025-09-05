import { Outlet } from "react-router-dom";
import { MessageSidebar } from "./MessageSidebar";

export function MessageLayout() {
  return (
    <div className="flex flex-1">
      <MessageSidebar />

      <Outlet />
    </div>
  );
}
