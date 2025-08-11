import { BrowserRouter } from "react-router-dom";
import AppRoutes from "./routes/AppRoutes";
import { AuthProvider } from "./auth/AuthContext";
import { WebSocketProvider } from "./providers/WebsocketProvider";

function App() {
  return (
    <BrowserRouter>
      <div style={{ flexGrow: 1, backgroundColor: "#313338" }}>
        <AuthProvider>
          <WebSocketProvider>
            <AppRoutes />
          </WebSocketProvider>
        </AuthProvider>
      </div>
    </BrowserRouter>
  );
}

export default App;
