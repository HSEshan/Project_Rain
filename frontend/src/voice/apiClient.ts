import apiClient from "../utils/apiClientBase";

export type VoiceJoinResponse = {
  room: string;
  token: string;
  /** Path on this origin that Caddy proxies to LiveKit, e.g. "/livekit" */
  url_path: string;
  identity: string;
  participants: string[];
};

export type VoiceParticipants = {
  channel_id: string;
  participants: string[];
};

/**
 * Deliberately throws rather than returning an empty result. Joining a voice
 * channel is a mutation the user is watching happen — swallowing the failure
 * would leave them staring at a dead panel.
 *
 * There is no matching `leave` call. Disconnecting from the room is what marks
 * you as gone: LiveKit tells the server through a webhook, which is the only
 * thing that also catches a refresh, a crash, or a closed laptop.
 */
export const joinVoiceChannel = async (
  channelId: string
): Promise<VoiceJoinResponse> => {
  const response = await apiClient.post(`/channels/${channelId}/voice/join`);
  return response.data;
};

export const getVoiceParticipants = async (
  channelId: string
): Promise<string[]> => {
  const response = await apiClient.get(
    `/channels/${channelId}/voice/participants`
  );
  return response.data.participants;
};

/**
 * The server returns a path, not an absolute URL — it has no reliable idea what
 * host the browser loaded the app from. LiveKit's signalling is a websocket, so
 * the scheme has to be ws/wss rather than http/https.
 */
export function livekitUrl(urlPath: string): string {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}${urlPath}`;
}
