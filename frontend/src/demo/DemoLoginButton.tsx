import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FiPlay } from "react-icons/fi";
import { Button, type ButtonProps } from "../shared/Button";
import { useAuth } from "../auth/AuthContext";
import { resetAllStores } from "../shared/resetStores";
import { useTourStore } from "../tour/tourStore";
import { getDemoStatus, postDemoLogin } from "./apiClient";

/**
 * One click into a working account, for someone who is not going to sign up.
 *
 * Renders nothing at all when the server has no demo (`DEMO_ENABLED` off), so
 * a private deployment of this codebase shows no trace of it. On success it
 * starts the orientation tour, because a visitor who has never seen the app is
 * exactly who the tour is for.
 */
export default function DemoLoginButton({
  size = "lg",
  variant = "secondary",
  full,
}: Pick<ButtonProps, "size" | "variant" | "full">) {
  const [available, setAvailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { login } = useAuth();
  const navigate = useNavigate();
  const startTour = useTourStore((state) => state.start);

  useEffect(() => {
    let cancelled = false;
    getDemoStatus().then((status) => {
      if (!cancelled) setAvailable(status.enabled);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleClick = async () => {
    setLoading(true);
    setError("");
    try {
      const session = await postDemoLogin();
      // The visitor may already be signed in as themselves in this tab; the
      // stores are per-account and would otherwise leak across the switch.
      resetAllStores();
      login(session.access_token);
      startTour();
      navigate("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the demo");
      setLoading(false);
    }
  };

  if (!available) return null;

  return (
    <div className={full ? "w-full" : undefined}>
      <Button
        variant={variant}
        size={size}
        full={full}
        icon={<FiPlay />}
        loading={loading}
        onClick={handleClick}
      >
        {loading ? "Preparing demo" : "Try the demo"}
      </Button>
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}
