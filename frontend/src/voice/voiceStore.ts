import {
  Room,
  RoomEvent,
  Track,
  type Participant,
  type RemoteParticipant,
  type RemoteTrack,
  type RemoteTrackPublication,
} from "livekit-client";
import { create } from "zustand";
import { eventBus } from "../utils/EventBus";
import { onResync } from "../shared/resync";
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
  /**
   * Whether you were muted before you deafened yourself, so undeafening can
   * put you back. Null means there is nothing to restore — either you are not
   * deafened, or you changed your mute by hand while deafened and that later
   * choice is the one to keep.
   */
  mutedBeforeDeafen: boolean | null;
  /**
   * Who is talking right now, as a map so a component can subscribe to one
   * person and re-render only when *that* boolean flips. An array here would
   * give every roster on screen a new identity on every speaker change.
   *
   * Only ever populated for the room we are connected to: LiveKit computes
   * this from audio levels, and we do not receive them for a room we are not
   * in. Nobody can see who is talking in a channel they have not joined, which
   * is also how Discord behaves.
   */
  speaking: Record<string, boolean>;
  /**
   * Remote users we currently hold audio for, which is exactly the set a volume
   * slider can do anything about. Not the roster: someone can be in the room
   * with no microphone published.
   */
  audible: string[];
  /** Master output, 0 to 1. Applies to everyone we can hear. */
  outputVolume: number;
  /** Per-person trim, 0 to 1, remembered across sessions. */
  userVolumes: Record<string, number>;
  /** Not in React state: mutating a Room does not re-render anything. */
  room: Room | null;

  getRoster: (channelId: string) => string[];
  fetchRoster: (channelId: string) => Promise<void>;
  join: (channelId: string) => Promise<void>;
  leave: () => Promise<void>;
  toggleMute: () => Promise<void>;
  toggleDeafen: () => Promise<void>;
  setOutputVolume: (volume: number) => void;
  setUserVolume: (userId: string, volume: number) => void;
  reset: () => void;
};

/**
 * Remote audio elements, kept out of React so nothing can unmount them.
 *
 * Keyed by track sid because that is what an unsubscribe gives us, and carrying
 * the user id because that is what a volume setting is attached to. One
 * participant can publish more than one audio track, so this is many-to-one.
 */
const audioElements = new Map<
  string,
  { element: HTMLAudioElement; userId: string }
>();

/**
 * Volume preferences live in `localStorage`, not on the server.
 *
 * "This person is too loud" is a fact about your speakers and your room, not
 * about your account, and it should not follow you to a machine where it is not
 * true. Every access is wrapped: private mode and disabled storage both throw,
 * and losing a volume preference must never be the thing that breaks joining a
 * call.
 */
const OUTPUT_VOLUME_KEY = "rain.voice.outputVolume";
const USER_VOLUMES_KEY = "rain.voice.userVolumes";

const clampVolume = (volume: number) => Math.min(1, Math.max(0, volume));

function readStoredOutputVolume(): number {
  try {
    const stored = localStorage.getItem(OUTPUT_VOLUME_KEY);
    if (stored === null) return 1;
    const parsed = Number.parseFloat(stored);
    return Number.isFinite(parsed) ? clampVolume(parsed) : 1;
  } catch {
    return 1;
  }
}

function readStoredUserVolumes(): Record<string, number> {
  try {
    const stored = localStorage.getItem(USER_VOLUMES_KEY);
    if (!stored) return {};
    const parsed: unknown = JSON.parse(stored);
    if (!parsed || typeof parsed !== "object") return {};
    // Rebuilt rather than trusted: this is the one input to the store that a
    // person can hand-edit, and a string where a number belongs would end up
    // in `element.volume`, which throws on a value outside 0 to 1.
    return Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>)
        .filter(([, value]) => typeof value === "number" && Number.isFinite(value))
        .map(([userId, value]) => [userId, clampVolume(value as number)])
    );
  } catch {
    return {};
  }
}

function persist(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Storage full, private mode, or disabled. The setting still applies to
    // this session; it just will not be here next time.
  }
}

function applyDeafen(deafened: boolean) {
  audioElements.forEach(({ element }) => {
    element.muted = deafened;
  });
}

/**
 * Push the current volumes onto every attached element.
 *
 * Multiplied rather than chosen between: the master is "everything is too
 * loud", the per-person trim is "this one is", and someone who has set both
 * means both. Deafen is deliberately not part of it — that is `element.muted`,
 * so undeafening restores the volume you had rather than resetting it to full.
 */
function applyVolumes() {
  const { outputVolume, userVolumes } = useVoiceStore.getState();
  audioElements.forEach(({ element, userId }) => {
    element.volume = clampVolume(outputVolume * (userVolumes[userId] ?? 1));
  });
}

/** The remote users we hold audio for, for the volume panel to list. */
function audibleUserIds(): string[] {
  return [...new Set([...audioElements.values()].map((entry) => entry.userId))];
}

function attachTrack(
  track: RemoteTrack,
  publication: RemoteTrackPublication,
  participant: RemoteParticipant
) {
  if (track.kind !== Track.Kind.Audio) return;
  const element = track.attach() as HTMLAudioElement;
  element.autoplay = true;
  element.muted = useVoiceStore.getState().deafened;
  element.style.display = "none";
  document.body.appendChild(element);
  // `identity` is the user id: the join token sets it that way, so every
  // volume preference is keyed by the same id the roster and the profile card
  // use. See the token claims in `rest_api/src/voice/tokens.py`.
  audioElements.set(publication.trackSid, {
    element,
    userId: participant.identity,
  });
  applyVolumes();
  useVoiceStore.setState({ audible: audibleUserIds() });
}

function detachTrack(track: RemoteTrack, publication: RemoteTrackPublication) {
  track.detach().forEach((element) => element.remove());
  audioElements.delete(publication.trackSid);
  useVoiceStore.setState({ audible: audibleUserIds() });
}

function detachAll() {
  audioElements.forEach(({ element }) => element.remove());
  audioElements.clear();
}

/**
 * When each channel's roster last changed from an authoritative source.
 *
 * A `fetchRoster` response is a snapshot of the moment it was *issued*, and a
 * VOICE_STATE event that lands while it is in flight describes a later moment.
 * Applying the response anyway rolls the roster back — and the roll-back that
 * matters is the one that removes *you* right after you joined, which is what
 * leaves the view stuck on "waiting for the roster to catch up".
 *
 * Module scope rather than store state: nothing renders from it.
 */
const rosterTouchedAt = new Map<string, number>();

function markRosterTouched(channelId: string) {
  rosterTouchedAt.set(channelId, Date.now());
}

/**
 * Ask the server again until it agrees that we are in the room we joined.
 *
 * The roster is delivered by an event (LiveKit webhook -> rest_api -> Redis ->
 * gateway -> here), and every hop is one where a single message can be lost:
 * an event published to a shard nobody is reading, a gateway that has not
 * registered this channel yet, a Redis blip. Losing it is not fatal to
 * anything except the display, but the display then says "waiting" forever,
 * because nothing was ever going to ask a second time.
 *
 * Bounded and self-cancelling: it stops the moment the server agrees, and the
 * moment we are no longer in that channel. Three tries over about ten seconds
 * is enough for a delivery hiccup and short enough not to paper over a real
 * outage.
 */
const RECONCILE_DELAYS_MS = [1500, 3000, 6000];

async function reconcileRoster(channelId: string, selfId: string | null) {
  for (const delay of RECONCILE_DELAYS_MS) {
    await new Promise((resolve) => setTimeout(resolve, delay));

    const state = useVoiceStore.getState();
    // Left, or switched channels, while we were waiting.
    if (state.activeChannelId !== channelId) return;
    // The event arrived on its own, which is the ordinary case.
    if (selfId && (state.rosters[channelId] ?? []).includes(selfId)) return;

    await state.fetchRoster(channelId);
  }
}

export const useVoiceStore = create<VoiceStore>((set, get) => ({
  rosters: {},
  activeChannelId: null,
  connecting: false,
  error: null,
  muted: false,
  deafened: false,
  mutedBeforeDeafen: null,
  speaking: {},
  audible: [],
  outputVolume: readStoredOutputVolume(),
  userVolumes: readStoredUserVolumes(),
  room: null,

  getRoster: (channelId) => get().rosters[channelId] ?? [],

  fetchRoster: async (channelId) => {
    const issuedAt = Date.now();
    try {
      const participants = await getVoiceParticipants(channelId);
      // Discard a snapshot that an event has already overtaken. Without this a
      // fetch issued before you joined can land after the event announcing you
      // and quietly take you back out of the room you are sitting in.
      const touchedAt = rosterTouchedAt.get(channelId);
      if (touchedAt !== undefined && touchedAt > issuedAt) return;

      markRosterTouched(channelId);
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
      markRosterTouched(channelId);
      set((state) => ({
        rosters: { ...state.rosters, [channelId]: session.participants },
      }));

      const room = new Room({ adaptiveStream: false, dynacast: false });

      room
        .on(RoomEvent.TrackSubscribed, attachTrack)
        .on(RoomEvent.TrackUnsubscribed, detachTrack)
        .on(RoomEvent.ActiveSpeakersChanged, (speakers: Participant[]) => {
          // Same guard as Disconnected: a late event from the room we just
          // left would otherwise paint speaking rings on the new one.
          if (get().room !== room) return;

          const next: Record<string, boolean> = {};
          speakers.forEach((speaker) => {
            if (speaker.identity) next[speaker.identity] = true;
          });

          // LiveKit already throttles this server-side, but it still fires with
          // an unchanged set — a silence of five seconds is five identical
          // empty arrays. Replacing state each time would re-render every
          // roster, tile and call bar on screen for no visible change, so the
          // comparison is the rate limit that matters.
          const current = get().speaking;
          const currentIds = Object.keys(current);
          const nextIds = Object.keys(next);
          if (
            currentIds.length === nextIds.length &&
            nextIds.every((id) => current[id])
          ) {
            return;
          }
          set({ speaking: next });
        })
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
          set({
            activeChannelId: null,
            room: null,
            connecting: false,
            speaking: {},
            audible: [],
          });
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
        mutedBeforeDeafen: null,
        speaking: {},
        error: micError,
      });

      // The SFU has accepted us, so the server's roster is about to include us
      // — unless the event saying so is lost, in which case nothing else would
      // ever ask again. Detached on purpose: joining is finished, and this is
      // a background correction that must not delay it.
      void reconcileRoster(channelId, session.identity ?? null);
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
      mutedBeforeDeafen: null,
      // Nobody is talking in a room we are not in, and there is nothing left to
      // turn the volume down on.
      speaking: {},
      audible: [],
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
    // Changing it by hand replaces whatever deafening remembered. Otherwise
    // undeafening would undo a choice made after it.
    set({ muted: next, mutedBeforeDeafen: null, error: null });
  },

  toggleDeafen: async () => {
    const { room, deafened, muted, mutedBeforeDeafen } = get();
    if (!room) return;
    const next = !deafened;
    applyDeafen(next);

    // Deafening also mutes, the way Discord does it: it would be rude to keep
    // talking to people you have stopped listening to.
    if (next) {
      await room.localParticipant.setMicrophoneEnabled(false);
      // Remember what you had, so undeafening can hand it back. Someone who
      // was talking before they deafened is not asking to be muted afterwards
      // as well; they used one control and expect one thing to change.
      set({ deafened: true, muted: true, mutedBeforeDeafen: muted });
      return;
    }

    // Undeafening. Nothing remembered (you muted or unmuted by hand while
    // deafened) means the current state is the one you chose, so leave it.
    if (mutedBeforeDeafen === null || mutedBeforeDeafen) {
      set({ deafened: false, mutedBeforeDeafen: null });
      return;
    }

    try {
      await room.localParticipant.setMicrophoneEnabled(true);
    } catch (error) {
      // The microphone can have gone away while you were deafened. Restoring
      // "unmuted" then has to fail visibly rather than leave the button
      // claiming you are live when nothing is being published.
      console.warn("Could not restore the microphone", error);
      set({
        deafened: false,
        muted: true,
        mutedBeforeDeafen: null,
        error: "No microphone available.",
      });
      return;
    }
    set({ deafened: false, muted: false, mutedBeforeDeafen: null, error: null });
  },

  setOutputVolume: (volume) => {
    const next = clampVolume(volume);
    set({ outputVolume: next });
    applyVolumes();
    persist(OUTPUT_VOLUME_KEY, String(next));
  },

  setUserVolume: (userId, volume) => {
    const next = clampVolume(volume);
    const userVolumes = { ...get().userVolumes, [userId]: next };
    set({ userVolumes });
    applyVolumes();
    persist(USER_VOLUMES_KEY, JSON.stringify(userVolumes));
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
      mutedBeforeDeafen: null,
      speaking: {},
      audible: [],
      room: null,
      // `outputVolume` and `userVolumes` deliberately survive. They are a
      // property of these speakers in this room, not of the account that
      // happened to be signed in, so signing out should not reset them.
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

  markRosterTouched(channelId);
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

// VOICE_STATE deltas missed during a disconnect leave the roster wrong in both
// directions, so re-read the snapshot for every channel we are tracking.
onResync(() => {
  const channelIds = Object.keys(useVoiceStore.getState().rosters);
  channelIds.forEach((channelId) => {
    void useVoiceStore.getState().fetchRoster(channelId);
  });
});
