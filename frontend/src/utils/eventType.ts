export enum EventType {
  MESSAGE = "message",
  CALL = "call",
  NOTIFICATION = "notification",
  FRIEND_REQUEST = "friend_request",
}

export type EventPayload = {
  event_id: string;
  event_type: string;
  sender_id: string;
  receiver_id: string;
  text: string;
  metadata?: Record<string, unknown>;
  timestamp: string; // ISO 8601 format
};
