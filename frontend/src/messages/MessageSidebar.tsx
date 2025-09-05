import { Link, useParams } from "react-router-dom";
import { useMessageStore } from "./messageStore";
import { useEffect } from "react";

export function MessageSidebar() {
  const { channels, unReads } = useMessageStore();
  const { dmId } = useParams<{ dmId: string }>();

  useEffect(() => {
    console.log(channels);
  }, [channels]);

  return (
    <div className="w-1/6 bg-gray-900 text-white flex flex-col items-center px-2 py-4 gap-4">
      {channels.map((channel) => (
        <Link
          to={`/dm/${channel.channel_id}`}
          key={channel.channel_id}
          className={`w-full h-10 rounded-sm flex items-center justify-center ${
            dmId === channel.channel_id ? "bg-blue-500" : "bg-gray-700"
          }`}
        >
          {channel.participants
            .map((participant) => participant.username)
            .join(", ")}
          {unReads.includes(channel.channel_id) && (
            <span className="relative top-[-10px] right-[-30px] w-3 h-3 bg-red-500 rounded-full" />
          )}
        </Link>
      ))}
    </div>
  );
}
