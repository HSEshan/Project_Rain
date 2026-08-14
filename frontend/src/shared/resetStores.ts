import { useChannelStore } from "./channelStore";
import { useMessageStore } from "./messageStore";
import { useUserStore } from "./userStore";
import { useGuildStore } from "../guild/guildStore";
import { useFriendStore } from "../friends/friendStore";
import { useVoiceStore } from "../voice/voiceStore";

/**
 * Drop every piece of per-account state. Call this on logout so the next
 * account that signs in on this tab never sees the previous one's data.
 */
export function resetAllStores() {
  useChannelStore.getState().reset();
  useMessageStore.getState().clearAllMessages();
  useUserStore.getState().clearUsers();
  useGuildStore.getState().reset();
  useFriendStore.getState().reset();
  // Also disconnects the SFU room — signing out must not leave a live mic
  useVoiceStore.getState().reset();
}
