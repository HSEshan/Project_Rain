import { useEffect } from "react";
import { FiMic, FiMicOff, FiPhoneOff, FiVolume2, FiVolumeX } from "react-icons/fi";
import { useAuth } from "../auth/AuthContext";
import { useUserStore } from "../shared/userStore";
import type { Channel } from "../shared/types";
import { useVoiceStore } from "./voiceStore";

function ParticipantTile({ userId }: { userId: string }) {
  const user = useUserStore((state) => state.users[userId]);
  const name = user?.username ?? "…";
  return (
    <div className="flex flex-col items-center gap-2 w-28 py-4 rounded-lg bg-gray-900">
      <div className="w-14 h-14 rounded-full bg-gray-700 text-white flex items-center justify-center text-xl">
        {name.charAt(0).toUpperCase()}
      </div>
      <span className="text-sm text-gray-300 truncate max-w-full px-2">{name}</span>
    </div>
  );
}

export default function VoiceChannelView({ channel }: { channel: Channel }) {
  const {
    activeChannelId,
    connecting,
    error,
    muted,
    deafened,
    join,
    leave,
    toggleMute,
    toggleDeafen,
    fetchRoster,
    getRoster,
  } = useVoiceStore();
  const { getCurrentUser } = useAuth();
  const fetchUsers = useUserStore((state) => state.fetchUsers);

  const connected = activeChannelId === channel.id;
  const participants = getRoster(channel.id);
  const currentUserId = getCurrentUser()?.id;

  // The roster is server state; anyone can be in here before we arrive
  useEffect(() => {
    void fetchRoster(channel.id);
  }, [channel.id, fetchRoster]);

  useEffect(() => {
    if (participants.length) void fetchUsers(participants);
  }, [participants, fetchUsers]);

  return (
    <div className="flex-1 flex flex-col">
      <div className="px-4 py-3 border-b border-gray-700 text-white font-semibold">
        🔊 {channel.name}
      </div>

      <div className="flex-1 flex flex-col items-center justify-center gap-8 p-6">
        {participants.length > 0 ? (
          <div className="flex flex-wrap gap-4 justify-center">
            {participants.map((userId) => (
              <ParticipantTile key={userId} userId={userId} />
            ))}
          </div>
        ) : (
          <p className="text-gray-500">Nobody is in here yet.</p>
        )}

        {error && <p className="text-red-400 text-sm max-w-md text-center">{error}</p>}

        {connected ? (
          <div className="flex items-center gap-3">
            <button
              onClick={() => void toggleMute()}
              title={muted ? "Unmute" : "Mute"}
              className={`p-3 rounded-full transition-colors ${
                muted
                  ? "bg-red-600 hover:bg-red-500"
                  : "bg-gray-700 hover:bg-gray-600"
              } text-white`}
            >
              {muted ? <FiMicOff /> : <FiMic />}
            </button>
            <button
              onClick={() => void toggleDeafen()}
              title={deafened ? "Undeafen" : "Deafen"}
              className={`p-3 rounded-full transition-colors ${
                deafened
                  ? "bg-red-600 hover:bg-red-500"
                  : "bg-gray-700 hover:bg-gray-600"
              } text-white`}
            >
              {deafened ? <FiVolumeX /> : <FiVolume2 />}
            </button>
            <button
              onClick={() => void leave()}
              title="Disconnect"
              className="p-3 rounded-full bg-red-600 hover:bg-red-500 text-white transition-colors"
            >
              <FiPhoneOff />
            </button>
          </div>
        ) : (
          <button
            onClick={() => void join(channel.id)}
            disabled={connecting}
            className="px-6 py-2 rounded-md bg-green-600 hover:bg-green-500 disabled:bg-gray-600 text-white transition-colors"
          >
            {connecting ? "Connecting…" : "Join voice"}
          </button>
        )}

        {connected && currentUserId && !participants.includes(currentUserId) && (
          <p className="text-xs text-gray-500">
            Connected. Waiting for the roster to catch up…
          </p>
        )}
      </div>
    </div>
  );
}
