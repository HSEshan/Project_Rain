export type Message = {
  id: string;
  content: string;
  sender_id: string;
  channel_id: string;
  created_at: string;
};

export enum ChannelType {
  DM = "dm",
  GROUP_DM = "group_dm",
  GUILD_TEXT = "guild_text",
  GUILD_VOICE = "guild_voice",
}

/** DMs and group DMs: private conversations, listed in the messages sidebar. */
export const DIRECT_CHANNEL_TYPES = [ChannelType.DM, ChannelType.GROUP_DM];

/**
 * Channels you can call in. Mirrors CALLABLE_CHANNEL_TYPES in libs: guild text
 * is the only kind that cannot carry voice.
 */
export const CALLABLE_CHANNEL_TYPES = [
  ChannelType.GUILD_VOICE,
  ChannelType.DM,
  ChannelType.GROUP_DM,
];

export const isDirectChannel = (channel?: Channel) =>
  !!channel && DIRECT_CHANNEL_TYPES.includes(channel.type);

export type Channel = {
  id: string;
  name?: string | null;
  type: ChannelType;
  guild_id?: string | null;
  description?: string | null;
  /** Group DMs only. Moves to the longest-standing member if the owner leaves. */
  owner_id?: string | null;
  created_at: string;
};

export type ChannelMember = {
  user_id: string;
  username: string;
  is_owner: boolean;
};
