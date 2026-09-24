import { useState } from "react";
import { FiEdit2 } from "react-icons/fi";
import { Button } from "../shared/Button";
import { Textarea } from "../shared/Input";
import { errorText } from "../shared/errors";
import {
  BIO_MAX_LENGTH,
  updateMyProfile,
  type UserProfile,
} from "./apiClient";
import { useProfileStore } from "./profileStore";

/**
 * The bio, and — on your own card — the only place in the app you edit
 * yourself.
 *
 * It is its own component rather than a block inside `ProfileCard` because it
 * is the first of a set: an avatar goes beside it, and the card should not
 * grow a second piece of edit state each time. The card stays a description of
 * a person; this owns the one field you can change.
 */
export default function ProfileBio({
  profile,
  editable,
}: {
  profile: UserProfile;
  editable: boolean;
}) {
  const applyProfile = useProfileStore((state) => state.applyProfile);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const startEditing = () => {
    setDraft(profile.bio ?? "");
    setError("");
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      // Empty means "clear it", which is `null` rather than "": the server
      // stores the absence of a bio, not an empty one, so that a card can tell
      // "never wrote one" from anything else.
      const next = await updateMyProfile({ bio: draft.trim() || null });
      applyProfile(next);
      setEditing(false);
    } catch (saveError) {
      setError(errorText(saveError, "Could not save that."));
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <div className="space-y-2">
        <Textarea
          label="About me"
          name="bio"
          rows={3}
          autoFocus
          // The server enforces this too, and its message names the number.
          // This is here so the limit is felt while typing rather than
          // discovered on save.
          maxLength={BIO_MAX_LENGTH}
          placeholder="A line or two about you."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="flex items-center justify-between gap-3">
          <span className="text-[11px] tabular-nums text-ink-400">
            {draft.length}/{BIO_MAX_LENGTH}
          </span>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setEditing(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={saving}
              onClick={save}
            >
              Save
            </Button>
          </div>
        </div>
        {error && <p className="text-xs text-red-300">{error}</p>}
      </div>
    );
  }

  // Somebody else's card with nothing written on it: render nothing rather
  // than an empty heading. There is no action to offer and no absence worth
  // pointing out.
  if (!profile.bio && !editable) return null;

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-400">
          About me
        </p>
        {editable && (
          <Button
            variant="ghost"
            size="sm"
            icon={<FiEdit2 size={13} />}
            onClick={startEditing}
          >
            {profile.bio ? "Edit" : "Add"}
          </Button>
        )}
      </div>

      {profile.bio ? (
        // `whitespace-pre-line` keeps the line breaks someone typed, and
        // `break-words` keeps a 190 character word from widening the modal.
        // Rendered as text: a bio is user-authored and never becomes markup.
        <p className="whitespace-pre-line break-words text-sm text-ink-200">
          {profile.bio}
        </p>
      ) : (
        <p className="text-sm text-ink-400">
          Nothing here yet. Say something about yourself.
        </p>
      )}
    </div>
  );
}
