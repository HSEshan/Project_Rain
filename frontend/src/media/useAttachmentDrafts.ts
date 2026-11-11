import { useCallback, useEffect, useRef, useState } from "react";
import type { Attachment } from "../shared/types";
import { errorText } from "../shared/errors";
import {
  MAX_ATTACHMENTS_PER_MESSAGE,
  preflightError,
  uploadAttachment,
} from "./apiClient";

export type AttachmentDraft = {
  localId: string;
  /** A local object URL, so the preview shows before the upload finishes. */
  previewUrl: string;
  /** 0 to 1 while uploading. */
  progress: number;
  /** Set once the server has stored it; its id is what the message sends. */
  attachment?: Attachment;
  error?: string;
};

/** A restored draft previews from its stored URL, which is not ours to revoke. */
const revokePreview = (url: string) => {
  if (url.startsWith("blob:")) URL.revokeObjectURL(url);
};

/**
 * Images waiting to go out with the next message in one composer.
 *
 * Each file uploads the moment it is chosen, not when Send is pressed. By the
 * time someone has typed a caption the upload is usually done, so sending is
 * as instant as a text message. The price is that a picked-then-removed image
 * was uploaded for nothing; the server sweeps those after an hour.
 *
 * Reset when the channel changes, so an image picked in one conversation can
 * never be sent into another.
 */
export function useAttachmentDrafts(channelId: string) {
  const [drafts, setDrafts] = useState<AttachmentDraft[]>([]);
  const [notice, setNotice] = useState("");
  // The live list, for revoking object URLs on unmount without re-subscribing
  const draftsRef = useRef(drafts);
  useEffect(() => {
    draftsRef.current = drafts;
  }, [drafts]);
  // Bumped on every reset, so an upload that finishes after its composer was
  // cleared (sent, or the channel changed) cannot write itself back in.
  const generation = useRef(0);

  const update = (localId: string, patch: Partial<AttachmentDraft>) =>
    setDrafts((current) =>
      current.map((draft) => (draft.localId === localId ? { ...draft, ...patch } : draft))
    );

  const clear = useCallback(() => {
    generation.current += 1;
    draftsRef.current.forEach((draft) => revokePreview(draft.previewUrl));
    setDrafts([]);
    setNotice("");
  }, []);

  useEffect(() => clear, [channelId, clear]);

  const add = (files: File[]) => {
    setNotice("");
    const room = MAX_ATTACHMENTS_PER_MESSAGE - draftsRef.current.length;
    if (files.length > room) {
      setNotice(`Up to ${MAX_ATTACHMENTS_PER_MESSAGE} images per message.`);
    }

    const round = generation.current;
    for (const file of files.slice(0, Math.max(room, 0))) {
      const refused = preflightError(file);
      if (refused) {
        setNotice(refused);
        continue;
      }
      const localId = crypto.randomUUID();
      setDrafts((current) => [
        ...current,
        { localId, previewUrl: URL.createObjectURL(file), progress: 0 },
      ]);
      uploadAttachment(file, (progress) => {
        if (generation.current === round) update(localId, { progress });
      })
        .then((attachment) => {
          if (generation.current === round) update(localId, { attachment, progress: 1 });
        })
        .catch((error) => {
          if (generation.current === round) {
            update(localId, { error: errorText(error, "Upload failed.") });
          }
        });
    }
  };

  /**
   * Put back images that were sent and refused. A rate-limited message is
   * dropped before the gateway claims anything, so these are still ours and
   * still unclaimed; their ids are as good as they were a moment ago. Only into
   * an empty composer: anything picked since is a newer intent than a resend.
   * The preview is the stored image, since the local object URL was revoked.
   */
  const restore = useCallback((sent: Attachment[]) => {
    if (sent.length === 0 || draftsRef.current.length > 0) return;
    setDrafts(
      sent.map((attachment) => ({
        localId: crypto.randomUUID(),
        previewUrl: attachment.url,
        progress: 1,
        attachment,
      }))
    );
  }, []);

  const remove = (localId: string) => {
    const draft = draftsRef.current.find((item) => item.localId === localId);
    if (draft) revokePreview(draft.previewUrl);
    setDrafts((current) => current.filter((item) => item.localId !== localId));
  };

  const uploading = drafts.some((draft) => !draft.attachment && !draft.error);
  const ready = drafts
    .map((draft) => draft.attachment)
    .filter((attachment): attachment is Attachment => !!attachment);
  const readyIds = ready.map((attachment) => attachment.id);

  return { drafts, notice, add, remove, clear, restore, uploading, ready, readyIds };
}
