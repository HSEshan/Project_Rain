import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Modal from "../shared/Modal";
import { useGuildStore } from "./guildStore";
import { useChannelStore } from "../shared/channelStore";
import { ChannelType } from "../shared/types";
import { postCreateGuildChannel } from "./apiClient";

export default function GuildChannelCreateModal() {
  const { channelModalGuildId, setChannelModalGuildId } = useGuildStore();
  const { addChannel } = useChannelStore();
  const navigate = useNavigate();
  const nameRef = useRef<HTMLInputElement>(null);
  const [type, setType] = useState<ChannelType>(ChannelType.GUILD_TEXT);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleClose = () => {
    setChannelModalGuildId(null);
    setError("");
    setIsLoading(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = nameRef.current?.value.trim();
    if (!name || !channelModalGuildId) return;

    setIsLoading(true);
    setError("");
    try {
      const res = await postCreateGuildChannel(channelModalGuildId, {
        name,
        type,
      });
      addChannel(res.data);
      const guildId = channelModalGuildId;
      handleClose();
      navigate(`/guild/${guildId}/channel/${res.data.id}`);
    } catch {
      setError("Could not create that channel");
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={!!channelModalGuildId}
      onClose={handleClose}
      title="Create Channel"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="channel-name"
            className="block text-sm font-medium text-gray-300 mb-2"
          >
            Channel Name *
          </label>
          <input
            id="channel-name"
            ref={nameRef}
            type="text"
            placeholder="new-channel"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            required
            disabled={isLoading}
          />
        </div>

        <div className="flex gap-3">
          {[ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE].map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setType(option)}
              className={`flex-1 px-4 py-2 rounded-md transition-colors ${
                type === option
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
              disabled={isLoading}
            >
              {option === ChannelType.GUILD_TEXT ? "💬 Text" : "🔊 Voice"}
            </button>
          ))}
        </div>

        {error && <p className="text-red-500">{error}</p>}

        <div className="flex gap-3 pt-4">
          <button
            type="button"
            onClick={handleClose}
            className="flex-1 px-4 py-2 text-gray-300 bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-md transition-colors"
          >
            {isLoading ? "Creating..." : "Create Channel"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
