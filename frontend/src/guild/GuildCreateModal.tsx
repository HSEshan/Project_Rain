import { useState, useRef } from "react";
import type { AxiosResponse } from "axios";
import { useGuildStore } from "./guildStore";
import { useChannelStore } from "../shared/channelStore";
import Modal from "../shared/Modal";
import { Button } from "../shared/Button";
import { Input, Textarea } from "../shared/Input";
import { errorText } from "../shared/errors";
import { postCreateGuild } from "./apiClient";

export default function GuildCreateModal() {
  const { modalOpen, setModalOpen, addGuild } = useGuildStore();
  const { fetchUserChannels } = useChannelStore();
  const guildNameRef = useRef<HTMLInputElement>(null);
  const guildDescriptionRef = useRef<HTMLTextAreaElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!guildNameRef.current?.value.trim()) return;

    setIsLoading(true);
    setError("");
    await postCreateGuild({
      name: guildNameRef.current?.value || "",
      description: guildDescriptionRef.current?.value || "",
    })
      .then(async (res: AxiosResponse) => {
        addGuild(res.data);
        // The guild ships with general-text / general-voice; pull them in
        await fetchUserChannels();
        setModalOpen(false);
      })
      .catch((err: unknown) => {
        setError(errorText(err, "Could not create that guild."));
      })
      .finally(() => setIsLoading(false));
  };

  const handleClose = () => {
    setModalOpen(false);
    setError("");
    setIsLoading(false);
  };

  return (
    <Modal
      isOpen={modalOpen}
      onClose={handleClose}
      title="Create a guild"
      description="You will get a text and a voice channel to start with."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Guild name"
          name="guild-name"
          ref={guildNameRef}
          placeholder="Weekend Raiders"
          required
          disabled={isLoading}
          autoFocus
        />
        <Textarea
          label="Description (optional)"
          name="guild-description"
          ref={guildDescriptionRef}
          placeholder="What is this guild for?"
          rows={3}
          disabled={isLoading}
        />

        {error && (
          <p className="rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
            {error}
          </p>
        )}

        <div className="flex gap-3 pt-1">
          <Button type="button" onClick={handleClose} disabled={isLoading} full>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={isLoading} full>
            {isLoading ? "Creating…" : "Create guild"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
