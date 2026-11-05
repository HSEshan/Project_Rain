import { useEffect, useState } from "react";
import { useMatch, useNavigate } from "react-router-dom";
import { FiHash, FiTrash2, FiVolume2 } from "react-icons/fi";
import Modal from "../shared/Modal";
import { Button } from "../shared/Button";
import { Input, Textarea } from "../shared/Input";
import { errorText } from "../shared/errors";
import { useChannelStore } from "../shared/channelStore";
import { ChannelType, type Channel } from "../shared/types";
import { deleteGuildIcon } from "../media/apiClient";
import {
  deleteGuild,
  deleteGuildBan,
  deleteGuildChannel,
  getGuildBans,
  patchGuild,
  type GuildBan,
} from "./apiClient";
import { useGuildStore } from "./guildStore";
import { GuildPermission, allows, useGuildStanding } from "./permissions";
import type { Guild } from "./types";

function ErrorNote({ text }: { text: string }) {
  if (!text) return null;
  return (
    <p className="rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
      {text}
    </p>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-medium uppercase tracking-wide text-ink-300">
      {children}
    </h3>
  );
}

function OverviewForm({ guild }: { guild: Guild }) {
  const replaceGuild = useGuildStore((state) => state.replaceGuild);
  const [name, setName] = useState(guild.name);
  const [description, setDescription] = useState(guild.description);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const unchanged =
    name.trim() === guild.name && description.trim() === guild.description;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setSaved(false);
    setError("");
    try {
      replaceGuild(await patchGuild(guild.id, { name, description }));
      setSaved(true);
    } catch (err) {
      setError(errorText(err, "Could not save those changes."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <Input
        label="Name"
        name="guild-name"
        value={name}
        onChange={(e) => {
          setName(e.target.value);
          setSaved(false);
        }}
        maxLength={100}
        required
        disabled={busy}
      />
      <Textarea
        label="Description"
        name="guild-description"
        value={description}
        onChange={(e) => {
          setDescription(e.target.value);
          setSaved(false);
        }}
        maxLength={300}
        rows={3}
        disabled={busy}
      />
      <ErrorNote text={error} />
      <div className="flex items-center justify-end gap-3">
        {saved && <span className="text-xs text-ink-400">Saved</span>}
        <Button
          type="submit"
          variant="primary"
          size="sm"
          loading={busy}
          disabled={unchanged || !name.trim()}
        >
          Save changes
        </Button>
      </div>
    </form>
  );
}

function RemoveIcon({ guild }: { guild: Guild }) {
  const replaceGuild = useGuildStore((state) => state.replaceGuild);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const remove = async () => {
    setBusy(true);
    setError("");
    try {
      replaceGuild(await deleteGuildIcon(guild.id));
    } catch (err) {
      setError(errorText(err, "Could not remove the icon."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-ink-300">Guild icon</span>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        onClick={() => void remove()}
        loading={busy}
      >
        Remove
      </Button>
      <ErrorNote text={error} />
    </div>
  );
}

function ChannelRow({ channel, guildId }: { channel: Channel; guildId: string }) {
  const removeChannel = useChannelStore((state) => state.removeChannel);
  const navigate = useNavigate();
  const viewing =
    useMatch("/guild/:guildId/channel/:channelId")?.params.channelId ===
    channel.id;
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const Icon = channel.type === ChannelType.GUILD_VOICE ? FiVolume2 : FiHash;

  const remove = async () => {
    setBusy(true);
    setError("");
    try {
      await deleteGuildChannel(channel.id);
      if (viewing) navigate(`/guild/${guildId}`);
      removeChannel(channel.id);
    } catch (err) {
      setError(errorText(err, "Could not delete that channel."));
      setBusy(false);
    }
  };

  return (
    <li className="space-y-2 rounded-lg px-2 py-1.5 hover:bg-white/[0.03]">
      <div className="flex items-center gap-2">
        <Icon size={14} className="shrink-0 text-ink-400" />
        <span className="min-w-0 flex-1 truncate text-sm text-ink-200">
          {channel.name}
        </span>
        {confirming ? (
          <>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setConfirming(false)}
              disabled={busy}
            >
              Keep
            </Button>
            <Button
              type="button"
              size="sm"
              variant="danger"
              onClick={() => void remove()}
              loading={busy}
            >
              Delete
            </Button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            aria-label={`Delete ${channel.name}`}
            className="rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-white/5 hover:text-red-300"
          >
            <FiTrash2 size={14} />
          </button>
        )}
      </div>
      {confirming && (
        <p className="text-xs text-ink-400">
          Its messages are deleted with it, for everyone.
        </p>
      )}
      <ErrorNote text={error} />
    </li>
  );
}

function BanList({ guildId }: { guildId: string }) {
  const [bans, setBans] = useState<GuildBan[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let current = true;
    getGuildBans(guildId)
      .then((found) => {
        if (current) setBans(found);
      })
      .catch((err) => {
        if (current) setError(errorText(err, "Could not load the ban list."));
      });
    return () => {
      current = false;
    };
  }, [guildId]);

  const lift = async (userId: string) => {
    setError("");
    try {
      await deleteGuildBan(guildId, userId);
      setBans((current) => current.filter((ban) => ban.user_id !== userId));
    } catch (err) {
      setError(errorText(err, "Could not lift that ban."));
    }
  };

  if (bans.length === 0 && !error) return null;

  return (
    <section className="space-y-2">
      <SectionTitle>Banned</SectionTitle>
      <ErrorNote text={error} />
      <ul className="space-y-0.5">
        {bans.map((ban) => (
          <li key={ban.user_id} className="flex items-center gap-2 px-2 py-1">
            <span className="min-w-0 flex-1 truncate text-sm text-ink-200">
              {ban.username}
            </span>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => void lift(ban.user_id)}
            >
              Lift ban
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function DeleteGuild({ guild, onDone }: { guild: Guild; onDone: () => void }) {
  const removeGuild = useGuildStore((state) => state.removeGuild);
  const navigate = useNavigate();
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const remove = async () => {
    setBusy(true);
    setError("");
    try {
      await deleteGuild(guild.id);
      navigate("/guild");
      removeGuild(guild.id);
      onDone();
    } catch (err) {
      setError(errorText(err, "Could not delete this guild."));
      setBusy(false);
    }
  };

  return (
    <section className="space-y-3 rounded-xl border border-red-500/20 p-3.5">
      <SectionTitle>Delete this guild</SectionTitle>
      <p className="text-sm text-ink-400">
        Every channel and message goes with it, for everyone, and this cannot be
        undone. Type <span className="text-white">{guild.name}</span> to confirm.
      </p>
      <Input
        name="guild-delete-confirm"
        aria-label="Guild name"
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
        autoComplete="off"
        disabled={busy}
      />
      <ErrorNote text={error} />
      <Button
        type="button"
        variant="danger"
        onClick={() => void remove()}
        loading={busy}
        disabled={typed !== guild.name}
        full
      >
        Delete guild
      </Button>
    </section>
  );
}

/** Rename, channels, and the owner's way out. Opened from the channel bar. */
export default function GuildSettingsModal() {
  const { settingsModalGuildId, setSettingsModalGuildId } = useGuildStore();
  const guild = useGuildStore((state) =>
    state.guilds.find((g) => g.id === settingsModalGuildId)
  );
  const channels = useChannelStore((state) => state.channels);
  const standing = useGuildStanding(settingsModalGuildId ?? undefined);
  const close = () => setSettingsModalGuildId(null);

  if (!guild) return null;

  const guildChannels = Object.values(channels).filter(
    (channel) => channel.guild_id === guild.id
  );

  return (
    <Modal isOpen onClose={close} title="Guild settings">
      <div className="space-y-6">
        {allows(standing, GuildPermission.MANAGE_GUILD) && (
          // Keyed so reopening on another guild starts from that guild's values
          <OverviewForm key={guild.id} guild={guild} />
        )}

        {allows(standing, GuildPermission.MANAGE_GUILD) && guild.icon_url && (
          <RemoveIcon guild={guild} />
        )}

        {allows(standing, GuildPermission.MANAGE_CHANNELS) && (
          <section className="space-y-2">
            <SectionTitle>Channels</SectionTitle>
            {guildChannels.length ? (
              <ul className="space-y-0.5">
                {guildChannels.map((channel) => (
                  <ChannelRow
                    key={channel.id}
                    channel={channel}
                    guildId={guild.id}
                  />
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-400">No channels yet.</p>
            )}
          </section>
        )}

        {allows(standing, GuildPermission.KICK) && (
          <BanList guildId={guild.id} />
        )}

        {allows(standing, GuildPermission.DELETE_GUILD) && (
          <DeleteGuild guild={guild} onDone={close} />
        )}
      </div>
    </Modal>
  );
}
