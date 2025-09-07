import { useState } from "react";
import LoginForm from "./LoginForm";
import SignupForm from "./SignupForm";

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);

  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-4">
      <div className="bg-gray-800 p-8 rounded-xl w-full max-w-md shadow-xl">
        {isLogin ? <LoginForm /> : <SignupForm setIsLogin={setIsLogin} />}
        <button
          className="mt-6 w-full text-sm text-blue-400 hover:underline"
          onClick={() => setIsLogin((prev) => !prev)}
        >
          {isLogin
            ? "Don't have an account? Sign up"
            : "Already have an account? Log in"}
        </button>
      </div>
    </div>
  );
}
