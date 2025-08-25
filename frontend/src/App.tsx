import { BrowserRouter } from "react-router-dom";
import AppRoutes from "./routes/AppRoutes";
import { AuthProvider } from "./auth/AuthContext";

function App() {
  return (
    <BrowserRouter>
      <div style={{ flexGrow: 1, backgroundColor: "#313338" }}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </div>
    </BrowserRouter>
  );
}

export default App;
