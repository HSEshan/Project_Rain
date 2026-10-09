import apiClient from "../utils/apiClientBase";
import type { Attachment } from "../shared/types";
import type { UserProfile } from "../profile/apiClient";
import type { Guild } from "../guild/types";

/**
 * Mirrors MAX_UPLOAD_BYTES in rest_api. Checked here only so an oversized file
 * fails before it is sent; the server's check is the real one.
 */
export const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;
/** Mirrors MAX_ATTACHMENTS_PER_MESSAGE in `libs.db`. */
export const MAX_ATTACHMENTS_PER_MESSAGE = 4;
/** What the file picker offers. The server decides from the bytes, not this. */
export const ACCEPTED_IMAGE_TYPES = "image/png,image/jpeg,image/webp,image/gif";

/**
 * One file as multipart form data.
 *
 * The explicit content type matters: the shared client defaults to JSON, and
 * axios converts a FormData body *to JSON* when the header says JSON, which
 * would send the server an object with no file in it. Naming multipart here
 * stops that, and the browser then fills in the boundary itself.
 */
function formFor(file: File): [FormData, { headers: Record<string, string> }] {
  const form = new FormData();
  form.append("file", file);
  return [form, { headers: { "Content-Type": "multipart/form-data" } }];
}

export const uploadAttachment = async (
  file: File,
  onProgress?: (fraction: number) => void
): Promise<Attachment> => {
  const [form, config] = formFor(file);
  const response = await apiClient.post("/uploads/attachments", form, {
    ...config,
    onUploadProgress: (event) => {
      if (onProgress && event.total) onProgress(event.loaded / event.total);
    },
  });
  return response.data;
};

export const putMyAvatar = async (file: File): Promise<UserProfile> => {
  const [form, config] = formFor(file);
  const response = await apiClient.put("/users/me/avatar", form, config);
  return response.data;
};

export const deleteMyAvatar = async (): Promise<UserProfile> => {
  const response = await apiClient.delete("/users/me/avatar");
  return response.data;
};

export const putGuildIcon = async (guildId: string, file: File): Promise<Guild> => {
  const [form, config] = formFor(file);
  const response = await apiClient.put(`/guilds/${guildId}/icon`, form, config);
  return response.data;
};

export const deleteGuildIcon = async (guildId: string): Promise<Guild> => {
  const response = await apiClient.delete(`/guilds/${guildId}/icon`);
  return response.data;
};

/** The sentence to show for a file refused before upload, or null if it may go. */
export function preflightError(file: File): string | null {
  if (!file.type.startsWith("image/")) {
    return "Only images can be uploaded: PNG, JPEG, WebP or GIF.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `Images must be ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB or smaller.`;
  }
  return null;
}
