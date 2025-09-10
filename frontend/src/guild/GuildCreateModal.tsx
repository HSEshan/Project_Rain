import { useState, useRef } from "react";
import { useGuildStore } from "./guildStore";
import Modal from "../shared/Modal";
import { postCreateGuild } from "./apiClient";
import type { AxiosResponse } from "axios";

export default function GuildCreateModal() {
  const { modalOpen, setModalOpen, setGuilds, guilds } = useGuildStore();
  const guildNameRef = useRef<HTMLInputElement>(null);
  const guildDescriptionRef = useRef<HTMLTextAreaElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!guildNameRef.current?.value.trim()) return;

    setIsLoading(true);
    await postCreateGuild({
      name: guildNameRef.current?.value || "",
      description: guildDescriptionRef.current?.value || "",
    })
      .then((res: AxiosResponse) => {
        setGuilds([...guilds, res.data]);
        setModalOpen(false);
      })
      .catch((err: Error) => {
        setError(err.message);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  const handleClose = () => {
    setModalOpen(false);
    setIsLoading(false);
  };

  return (
    <Modal isOpen={modalOpen} onClose={handleClose} title="Create Guild">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="guild-name"
            className="block text-sm font-medium text-gray-300 mb-2"
          >
            Guild Name *
          </label>
          <input
            id="guild-name"
            ref={guildNameRef}
            type="text"
            placeholder="Enter guild name"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            required
            disabled={isLoading}
          />
        </div>

        <div>
          <label
            htmlFor="guild-description"
            className="block text-sm font-medium text-gray-300 mb-2"
          >
            Description (Optional)
          </label>
          <textarea
            id="guild-description"
            ref={guildDescriptionRef}
            placeholder="Enter guild description"
            rows={3}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            disabled={isLoading}
          />
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
            {isLoading ? "Creating..." : "Create Guild"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
