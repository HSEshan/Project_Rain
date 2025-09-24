import { useNavigate } from "react-router-dom";
import Aurora from "./Aurora";

export default function LandingPage() {
  const navigate = useNavigate();
  return (
    //background
    <div className="min-h-screen bg-gray-900 relative z-10">
      <Aurora amplitude={1.8} />
      <div className="w-2/3 mx-auto flex flex-col items-center justify-center relative z-20">
        <h1 className="text-6xl text-white font-bold">
          Elevate your comms now
        </h1>
        <h2 className="text-5xl text-white font-bold mt-6">
          with <span className="text-cyan-500">Rain</span>
        </h2>
        <button
          onClick={() => navigate("/login")}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md mt-8"
        >
          Start Now
        </button>
      </div>
    </div>
  );
}
