import { useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../utils/apiClient";
import { useAuth } from "../auth/AuthContext";

export default function SignupForm() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
  });

  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [generalError, setGeneralError] = useState("");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setErrors((prev) => ({ ...prev, [e.target.name]: "" }));
    setGeneralError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setGeneralError("");

    try {
      const res = await apiClient.post("/auth/register", formData);

      // Optionally: auto-login after successful signup
      const loginRes = await apiClient.post("/auth/login", {
        login: formData.username,
        password: formData.password,
      });

      login(loginRes.data.access_token);
      navigate("/home");
    } catch (err: any) {
      if (err.response?.status === 422) {
        const fieldErrors: { [key: string]: string } = {};
        for (const detail of err.response.data.detail) {
          const field = detail.loc?.[1];
          const msg = detail.msg;
          if (field) {
            fieldErrors[field] = msg;
          }
        }
        setErrors(fieldErrors);
      } else {
        setGeneralError("Signup failed. Please try again.");
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-2xl font-semibold text-center mb-4">Sign Up</h2>

      <input
        type="text"
        name="username"
        placeholder="Username"
        value={formData.username}
        onChange={handleChange}
        className="w-full p-2 bg-gray-700 text-white rounded"
      />
      {errors.username && (
        <p className="text-red-400 text-sm">{errors.username}</p>
      )}

      <input
        type="email"
        name="email"
        placeholder="Email"
        value={formData.email}
        onChange={handleChange}
        className="w-full p-2 bg-gray-700 text-white rounded"
      />
      {errors.email && <p className="text-red-400 text-sm">{errors.email}</p>}

      <input
        type="password"
        name="password"
        placeholder="Password"
        value={formData.password}
        onChange={handleChange}
        className="w-full p-2 bg-gray-700 text-white rounded"
      />
      {errors.password && (
        <p className="text-red-400 text-sm">{errors.password}</p>
      )}

      {generalError && <p className="text-red-400 text-sm">{generalError}</p>}

      <button
        type="submit"
        className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
      >
        Sign Up
      </button>
    </form>
  );
}
