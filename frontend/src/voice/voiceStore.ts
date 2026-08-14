import {
  Room,
  RoomEvent,
  Track,
  type RemoteTrack,
  type RemoteTrackPublication,
} from "livekit-client";
import { create } from "zustand";
import { eventBus } from "../utils/EventBus";
import { EventAction, EventType, type EventPayload } from "../utils/eventType";
import { getVoiceParticipants, joinVoiceChannel, livekitUrl } from "./apiClient";

/**
 * One voice session at a time, plus the roster of every voice channel we know
 * about.
 *
 * `rosters` mirrors what LiveKit reports, relayed by the server as VOICE_STATE
 * events, and drives the participant list under each channel in the sidebar —
 * which people who have not joined still need to see. This client never tells
 * the server who is in a room: it used to, and a refresh or a crash then left
 * the user listed forever. Connecting and disconnecting the `Room` is the only
 * thing that changes presence now.
 */

type VoiceStore = {
  rosters: Record<string, string[]>;
  activeChannelId: string | null;
  connecting: boolean;
  error: string | null;
  muted: boolean;
  deafened: boolean;
  /** Not in React state: mutating a Room does not re-render anything. */
  room: Room | null;

  getRoster: (channelId: string) => string[];
  fetchRoster: (channelId: string) => Promise<void>;
  join: (channelId: string) => Promise<void>;
  leave: () => Promise<void>;
  toggleMute: () => Promise<void>;
  toggleDeafen: () => Promise<void>;
  reset: () => void;
};

/** Remote audio elements, kept out of React so nothing can unmount them. */
const audioElements = new Map<string, HTMLAudioElement>();

function applyDeafen(deafened: boolean) {
  audioElements.forEach((el) => {
    el.muted = deafened;
  });
}

function attachTrack(track: RemoteTrack, publication: RemoteTrackPublication) {
  if (track.kind !== Track.Kind.Audio) return;
  const element = track.attach() as HTMLAudioElement;
  element.autoplay = true;
  element.muted = useVoiceStore.getState().deafened;
  element.style.display = "none";
  document.body.appendChild(element);
  audioElements.set(publication.trackSid, element);
}

function detachTrack(track: RemoteTrack, publication: RemoteTrackPublication) {
  track.detach().forEach((element) => element.remove());
  audioElements.delete(publication.trackSid);
}

function detachAll() {
  audioElements.forEach((element) => element.remove());
  audioElements.clear();
}

export const useVoiceStore = create<VoiceStore>((set, get) => ({
  rosters: {},
  activeChannelId: null,
  connecting: false,
  error: null,
  muted: false,
  deafened: false,
  room: null,

  getRoster: (channelId) => get().rosters[channelId] ?? [],

  fetchRoster: async (channelId) => {
    try {
      const participants = await getVoiceParticipants(channelId);
      set((state) => ({
        rosters: { ...state.rosters, [channelId]: participants },
      }));
    } catch (error) {
      console.error("Failed to fetch voice participants", error);
    }
  },

  join: async (channelId) => {
    if (get().activeChannelId === channelId || get().connecting) return;
    // Discord-style: joining a second channel leaves the first
    if (get().activeChannelId) await get().leave();

    set({ connecting: true, error: null });
    try {
      const session = await joinVoiceChannel(channelId);

      // Apply the snapshot *before* connecting, not after. Our own arrival
      // comes back as a VOICE_STATE event while `connect` is still running,
      // and setting this snapshot afterwards would overwrite it — leaving the
      // panel insisting nobody is in a room we are demonstrably in.
      set((state) => ({
        rosters: { ...state.rosters, [channelId]: session.participants },
      }));

      const room = new Room({ adaptiveStream: false, dynacast: false });

      room
        .on(RoomEvent.TrackSubscribed, attachTrack)
        .on(RoomEvent.TrackUnsubscribed, detachTrack)
        .on(RoomEvent.Disconnected, () => {
          // Server-side kick, network loss, or our own leave() — either way the
          // session is over and the UI must stop claiming we are connected.
          //
          // Only if it is still *this* room, though. Switching channels tears
          // down the old room while the new one is connecting, and a late
          // event from the old one would otherwise wipe the new session's
          // state and leave the user connected but shown as disconnected.
          if (get().room !== room) return;
          detachAll();
          set({ activeChannelId: null, room: null, connecting: false });
        });

      await room.connect(livekitUrl(session.url_path), session.token);

      // Publishing is a separate failure from connecting. No microphone, or a
      // denied permission prompt, should still leave you able to listen —
      // dropping the whole session for it would be worse than joining muted.
      let micError: string | null = null;
      try {
        await room.localParticipant.setMicrophoneEnabled(true);
      } catch (error) {
        console.warn("Could not enable the microphone", error);
        micError = "No microphone available — you joined muted.";
      }

      // Deliberately does not touch `rosters` — see above
      set({
        room,
        activeChannelId: channelId,
        connecting: false,
        muted: micError !== null,
        deafened: false,
        error: micError,
      });
    } catch (error) {
      console.error("Failed to join voice channel", error);
      set({
        connecting: false,
        activeChannelId: null,
        room: null,
        error:
          error instanceof Error ? error.message : "Could not join voice channel",
      });
      // Nothing to undo on the server: a token is not a connection, and the
      // roster is only written once LiveKit sees someone actually join.
    }
  },

  leave: async () => {
    const { room, activeChannelId } = get();
    if (!activeChannelId) return;

    // Disconnecting *is* the leave. LiveKit reports it to the server, which is
    // what keeps the roster right for a refresh or a crash too.
    await room?.disconnect();
    detachAll();
    set({
      activeChannelId: null,
      room: null,
      muted: false,
      deafened: false,
      // Whatever went wrong applied to the session that just ended
      error: null,
    });
  },

  toggleMute: async () => {
    const { room, muted } = get();
    if (!room) return;
    const next = !muted;
    try {
      await room.localParticipant.setMicrophoneEnabled(!next);
    } catch (error) {
      // Unmuting is where a missing or refused microphone surfaces
      console.warn("Could not change the microphone state", error);
      set({ muted: true, error: "No microphone available." });
      return;
    }
    set({ muted: next, error: null });
  },

  toggleDeafen: async () => {
    const { room, deafened } = get();
    if (!room) return;
    const next = !deafened;
    applyDeafen(next);
    // Deafening also mutes, the way Discord does it: it would be rude to keep
    // talking to people you have stopped listening to.
    if (next) {
      await room.localParticipant.setMicrophoneEnabled(false);
      set({ deafened: true, muted: true });
    } else {
      set({ deafened: false });
    }
  },

  reset: () => {
    get().room?.disconnect();
    detachAll();
    set({
      rosters: {},
      activeChannelId: null,
      connecting: false,
      error: null,
      muted: false,
      deafened: false,
      room: null,
    });
  },
}));

/**
 * Presence for everyone who is not in the room. VOICE_STATE is channel
 * addressed, so it reaches every member of the voice channel whether or not
 * they are connected to its SFU room.
 */
eventBus.on(EventType.VOICE_STATE, (event: EventPayload) => {
  const metadata = event.metadata as
    | { action?: string; channel_id?: string; user_id?: string }
    | undefined;
  const channelId = metadata?.channel_id;
  const userId = metadata?.user_id;
  if (!channelId || !userId) return;

  useVoiceStore.setState((state) => {
    const current = state.rosters[channelId] ?? [];
    const joined = metadata.action === EventAction.VOICE_JOINED;
    const next = joined
      ? current.includes(userId)
        ? current
        : [...current, userId]
      : current.filter((id) => id !== userId);
    return { rosters: { ...state.rosters, [channelId]: next } };
  });
});
