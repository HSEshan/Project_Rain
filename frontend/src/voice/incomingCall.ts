import { create } from "zustand";
import { readUser } from "../auth/tokenStore";
import { eventBus } from "../utils/EventBus";
import { EventAction, EventType, type EventPayload } from "../utils/eventType";
import { useVoiceStore } from "./voiceStore";

/**
 * Calls that are ringing for you: someone started a call in a DM or group DM
 * you belong to, and you are not in it.
 *
 * Before this, the only sign of a call was a green dot on the DM's sidebar row,
 * which on a phone sits inside a closed drawer. Someone who was not already
 * looking at that conversation had no way to know they were being called.
 *
 * **What rings** is the VOICE_STATE join that takes a channel's roster from
 * nobody to one person, the moment a call starts. Later joins into a running
 * group call do not ring again. It needs nothing from the server: that event
 * already reaches every member of the channel, joined or not.
 *
 * **A ring ends** when the caller's call ends (the roster empties), when you
 * join it, when you dismiss it, or after `RING_MS`. Guild voice channels never
 * ring, they are places rather than calls; the banner filters on channel type
 * because the channel may not be loaded yet when the event lands.
 *
 * Imports `voiceStore`, so its VOICE_STATE handler is registered first and the
 * roster this one reads already includes the join.
 */

export const RING_MS = 30_000;

export type IncomingCall = {
  channelId: string;
  callerId: string;
  startedAt: number;
};

type IncomingCallStore = {
  calls: Record<string, IncomingCall>;
  dismiss: (channelId: string) => void;
  reset: () => void;
};

const timers = new Map<string, ReturnType<typeof setTimeout>>();

function clearTimer(channelId: string) {
  const timer = timers.get(channelId);
  if (timer) clearTimeout(timer);
  timers.delete(channelId);
}

export const useIncomingCallStore = create<IncomingCallStore>((set) => ({
  calls: {},
  dismiss: (channelId) => {
    clearTimer(channelId);
    set((state) => {
      if (!state.calls[channelId]) return state;
      const calls = { ...state.calls };
      delete calls[channelId];
      return { calls };
    });
  },
  reset: () => {
    timers.forEach((timer) => clearTimeout(timer));
    timers.clear();
    set({ calls: {} });
  },
}));

eventBus.on(EventType.VOICE_STATE, (event: EventPayload) => {
  const metadata = event.metadata as
    | { action?: string; channel_id?: string; user_id?: string }
    | undefined;
  const channelId = metadata?.channel_id;
  const callerId = metadata?.user_id;
  if (!channelId || !callerId || metadata.action !== EventAction.VOICE_JOINED) {
    return;
  }

  if (callerId === readUser()?.id) return;
  const voice = useVoiceStore.getState();
  if (voice.activeChannelId === channelId) return;
  const roster = voice.rosters[channelId] ?? [];
  if (roster.length !== 1 || roster[0] !== callerId) return;

  clearTimer(channelId);
  timers.set(
    channelId,
    setTimeout(() => useIncomingCallStore.getState().dismiss(channelId), RING_MS)
  );
  useIncomingCallStore.setState((state) => ({
    calls: {
      ...state.calls,
      [channelId]: { channelId, callerId, startedAt: Date.now() },
    },
  }));
});

// Stop ringing once the call is over or you are in it, from whichever page.
useVoiceStore.subscribe((voice) => {
  const { calls, dismiss } = useIncomingCallStore.getState();
  Object.keys(calls).forEach((channelId) => {
    const ended = (voice.rosters[channelId] ?? []).length === 0;
    if (ended || voice.activeChannelId === channelId) dismiss(channelId);
  });
});
