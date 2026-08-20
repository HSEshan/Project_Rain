import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FiHash, FiVolume2 } from "react-icons/fi";
import Modal from "../shared/Modal";
import { Button } from "../shared/Button";
import { Input } from "../shared/Input";
import { errorText } from "../shared/errors";
import { useGuildStore } from "./guildStore";
import { useChannelStore } from "../shared/channelStore";
import { ChannelType } from "../shared/types";
import { postCreateGuildChannel } from "./apiClient";

const OPTIONS = [
  {
    type: ChannelType.GUILD_TEXT,
    label: "Text",
    hint: "Messages and history",
    Icon: FiHash,
  },
  {
    type: ChannelType.GUILD_VOICE,
    label: "Voice",
    hint: "Live audio on the SFU",
    Icon: FiVolume2,
  },
];

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
    } catch (err) {
      setError(errorText(err, "Could not create that channel."));
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={!!channelModalGuildId}
      onClose={handleClose}
      title="Create a channel"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-2 gap-2.5">
          {OPTIONS.map((option) => (
            <button
              key={option.type}
              type="button"
              onClick={() => setType(option.type)}
              disabled={isLoading}
              className={`flex flex-col items-start gap-1 rounded-xl border p-3.5 text-left transition-all ${
                type === option.type
                  ? "border-rain-400/40 bg-rain-400/[0.08] text-white"
                  : "border-white/[0.07] bg-white/[0.02] text-ink-300 hover:border-white/15"
              }`}
            >
              <option.Icon
                size={17}
                className={type === option.type ? "text-rain-300" : ""}
              />
              <span className="text-sm font-medium">{option.label}</span>
              <span className="text-[11px] text-ink-400">{option.hint}</span>
            </button>
          ))}
        </div>

        <Input
          label="Channel name"
          name="channel-name"
          ref={nameRef}
          placeholder="new-channel"
          required
          disabled={isLoading}
          autoFocus
        />

        {error && (
          <p className="rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
            {error}
          </p>
        )}

        <div className="flex gap-3">
          <Button type="button" onClick={handleClose} disabled={isLoading} full>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={isLoading} full>
            {isLoading ? "Creating…" : "Create channel"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
