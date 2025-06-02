import axios from "axios";
import { Cookies } from "react-cookie"; // Import Cookies class

const cookies = new Cookies(); // Create an instance of Cookies

const apiClient = axios.create({
  baseURL: "http://localhost:8000", // Replace with your FastAPI base URL
  headers: {
    "Content-Type": "application/json",
  },
});

// Axios interceptor to add Authorization header from cookies
apiClient.interceptors.request.use(
  (config) => {
    const token = cookies.get("token"); // Retrieve the token from cookies

    if (token) {
      // Attach token to Authorization header
      config.headers["Authorization"] = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default apiClient;
