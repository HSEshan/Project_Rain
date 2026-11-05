import { useEffect, useState } from "react";
import { FiCheck, FiCopy, FiLink, FiTrash2 } from "react-icons/fi";
import { Button } from "../shared/Button";
import { errorText } from "../shared/errors";
import {
  deleteInviteLink,
  getInviteLinks,
  postInviteLink,
  type InviteLink,
} from "./apiClient";

const EXPIRY_OPTIONS = [
  { label: "1 hour", hours: 1 },
  { label: "1 day", hours: 24 },
  { label: "7 days", hours: 24 * 7 },
  { label: "Never", hours: null },
];

const USE_OPTIONS = [
  { label: "No limit", uses: null },
  { label: "1 use", uses: 1 },
  { label: "5 uses", uses: 5 },
  { label: "25 uses", uses: 25 },
];

const SELECT =
  "h-9 w-full rounded-lg border border-white/10 bg-ink-850/80 px-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-rain-400/60";

const urlFor = (code: string) => `${window.location.origin}/invite/${code}`;

function describe(link: InviteLink) {
  const uses =
    link.max_uses === null
      ? `${link.uses} ${link.uses === 1 ? "use" : "uses"}`
      : `${link.uses} of ${link.max_uses} uses`;
  const expiry = link.expires_at
    ? `expires ${new Date(link.expires_at).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      })}`
    : "never expires";
  return `${uses}, ${expiry}`;
}

function LinkRow({
  link,
  onRevoke,
  onError,
}: {
  link: InviteLink;
  onRevoke: (code: string) => void;
  onError: (text: string) => void;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(urlFor(link.code));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Refused outside a secure context, or by a permission prompt
      onError("Could not copy that. Select the link and copy it by hand.");
    }
  };

  return (
    <li className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-2.5">
      <div className="flex items-center gap-1.5">
        <input
          readOnly
          value={urlFor(link.code)}
          aria-label="Invite link"
          onFocus={(e) => e.target.select()}
          className="min-w-0 flex-1 bg-transparent text-xs text-ink-200 focus:outline-none"
        />
        <button
          type="button"
          onClick={() => void copy()}
          aria-label="Copy link"
          className="shrink-0 rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-white/5 hover:text-white"
        >
          {copied ? <FiCheck size={14} /> : <FiCopy size={14} />}
        </button>
        <button
          type="button"
          onClick={() => onRevoke(link.code)}
          aria-label="Revoke link"
          className="shrink-0 rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-white/5 hover:text-red-300"
        >
          <FiTrash2 size={14} />
        </button>
      </div>
      <p className="mt-1 text-[11px] text-ink-400">{describe(link)}</p>
    </li>
  );
}

/** Links anyone can use. The server lists what this viewer may see and revoke. */
export default function GuildInviteLinks({ guildId }: { guildId: string }) {
  const [links, setLinks] = useState<InviteLink[]>([]);
  const [useIndex, setUseIndex] = useState(0);
  const [expiryIndex, setExpiryIndex] = useState(2);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let current = true;
    getInviteLinks(guildId)
      .then((found) => {
        if (current) setLinks(found);
      })
      .catch((err) => {
        if (current) setError(errorText(err, "Could not load invite links."));
      });
    return () => {
      current = false;
    };
  }, [guildId]);

  const create = async () => {
    setBusy(true);
    setError("");
    try {
      const link = await postInviteLink(guildId, {
        expires_in_hours: EXPIRY_OPTIONS[expiryIndex].hours,
        max_uses: USE_OPTIONS[useIndex].uses,
      });
      setLinks((current) => [link, ...current]);
    } catch (err) {
      setError(errorText(err, "Could not make that link."));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (code: string) => {
    setError("");
    try {
      await deleteInviteLink(guildId, code);
      setLinks((current) => current.filter((link) => link.code !== code));
    } catch (err) {
      setError(errorText(err, "Could not revoke that link."));
    }
  };

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-300">
        Invite link
      </h4>
      <p className="text-xs text-ink-400">Anyone with the link can join.</p>
      <div className="flex items-center gap-2">
        <select
          aria-label="Expires after"
          className={SELECT}
          value={expiryIndex}
          onChange={(e) => setExpiryIndex(Number(e.target.value))}
        >
          {EXPIRY_OPTIONS.map((option, index) => (
            <option key={option.label} value={index}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Maximum uses"
          className={SELECT}
          value={useIndex}
          onChange={(e) => setUseIndex(Number(e.target.value))}
        >
          {USE_OPTIONS.map((option, index) => (
            <option key={option.label} value={index}>
              {option.label}
            </option>
          ))}
        </select>
        <Button
          type="button"
          size="sm"
          icon={<FiLink size={13} />}
          onClick={() => void create()}
          loading={busy}
        >
          Create
        </Button>
      </div>
      {error && <p className="text-xs text-red-300">{error}</p>}
      {links.length > 0 && (
        <ul className="max-h-44 space-y-1.5 overflow-y-auto">
          {links.map((link) => (
            <LinkRow
              key={link.code}
              link={link}
              onRevoke={(code) => void revoke(code)}
              onError={setError}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
