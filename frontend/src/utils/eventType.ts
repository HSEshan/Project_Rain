export enum EventType {
  MESSAGE = "message",
  CALL = "call",
  NOTIFICATION = "notification",
  FRIEND_REQUEST = "friend_request",
  // Presence only — someone joined or left a voice channel. The audio itself
  // is between the browser and the SFU and never appears on this socket.
  VOICE_STATE = "voice_state",
}

/** Values of `metadata.action`. Mirrors `EventAction` in libs. */
export enum EventAction {
  FRIEND_REQUEST_RECEIVED = "friend_request_received",
  FRIEND_REQUEST_ACCEPTED = "friend_request_accepted",
  GUILD_INVITE_RECEIVED = "guild_invite_received",
  GUILD_INVITE_REMOVED = "guild_invite_removed",
  CHANNELS_CHANGED = "channels_changed",
  VOICE_JOINED = "voice_joined",
  VOICE_LEFT = "voice_left",
}

/** What kind of thing an event is addressed to. Mirrors `TargetType` in libs. */
export enum TargetType {
  USER = "user",
  CHANNEL = "channel",
}

export type EventPayload = {
  event_id: string;
  event_type: string;
  sender_id: string;
  /**
   * Deprecated. A channel id for `message` and `voice_state`, a user id for
   * `notification` and `friend_request`, with nothing here saying which.
   * `target_type`/`target_id` replace it; the server still sends both, so
   * nothing has to move until the old field is dropped.
   */
  receiver_id: string;
  target_type?: TargetType;
  target_id?: string;
  text: string;
  metadata?: Record<string, unknown>;
  timestamp: string; // ISO 8601 format
};
