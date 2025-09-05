import axios from "axios";
import { Cookies } from "react-cookie";

const cookies = new Cookies();

const apiHost = import.meta.env.VITE_HOST;

const apiClient = axios.create({
  baseURL: `http://${apiHost}:8000/api`,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add Authorization header if token exists
apiClient.interceptors.request.use(
  (config) => {
    const token = cookies.get("token");
    if (token) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export default apiClient;
