import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import Avatar from "../shared/Avatar";
import { Button } from "../shared/Button";
import EmptyState from "../shared/EmptyState";
import Spinner from "../shared/Spinner";
import { errorText } from "../shared/errors";
import {
  getInviteLinkPreview,
  postAcceptInviteLink,
  type InviteLinkPreview,
} from "./apiClient";
import { useGuildStore } from "./guildStore";
import { rememberInvite } from "./pendingInvite";

/**
 * Where an invite link lands. Public, because the person holding the link may not
 * have an account yet: they see what they are being invited to first, and go
 * through sign-in only to accept it.
 */
export default function InvitePage() {
  const { code = "" } = useParams<{ code: string }>();
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const [preview, setPreview] = useState<InviteLinkPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState("");
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let current = true;
    getInviteLinkPreview(code)
      .then((found) => {
        if (current) setPreview(found);
      })
      .catch((err) => {
        if (current) {
          setFailure(errorText(err, "This invite is invalid or has expired."));
        }
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [code]);

  const join = async () => {
    setJoining(true);
    setError("");
    try {
      const { guild_id } = await postAcceptInviteLink(code);
      // Before navigating: `GuildLayout` sends away anyone not in the guild
      await useGuildStore.getState().fetchUserGuilds();
      navigate(`/guild/${guild_id}`, { replace: true });
    } catch (err) {
      setError(errorText(err, "Could not join this guild."));
      setJoining(false);
    }
  };

  const signIn = () => {
    rememberInvite(code);
    navigate("/login");
  };

  return (
    <div className="flex min-h-dvh items-center justify-center bg-ink-950 p-4">
      {loading || isLoading ? (
        <Spinner className="h-7 w-7" />
      ) : !preview ? (
        <div className="w-full max-w-sm">
          <EmptyState title="This invite will not work" hint={failure} />
          <Button to="/" full>
            Go to Rain
          </Button>
        </div>
      ) : (
        <div className="glass w-full max-w-sm rounded-3xl border-white/10 bg-ink-850/95 p-6 text-center">
          <div className="flex justify-center">
            <Avatar
              name={preview.guild_name}
              seed={code}
              src={preview.icon_url ?? null}
              size="lg"
            />
          </div>
          <p className="mt-4 text-sm text-ink-400">You have been invited to</p>
          <h1 className="mt-1 break-words text-xl font-semibold text-white">
            {preview.guild_name}
          </h1>
          {preview.guild_description && (
            <p className="mt-2 break-words text-sm text-ink-300">
              {preview.guild_description}
            </p>
          )}
          <p className="mt-2 text-xs text-ink-400">
            {preview.member_count}{" "}
            {preview.member_count === 1 ? "member" : "members"}
          </p>

          {error && (
            <p className="mt-4 rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
              {error}
            </p>
          )}

          <div className="mt-5">
            {isAuthenticated ? (
              <Button
                variant="primary"
                onClick={() => void join()}
                loading={joining}
                full
              >
                Join guild
              </Button>
            ) : (
              <Button variant="primary" onClick={signIn} full>
                Sign in to join
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
