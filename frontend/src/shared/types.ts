export type Message = {
  id: string;
  content: string;
  sender_id: string;
  channel_id: string;
  created_at: string;
};

export enum ChannelType {
  DM = "dm",
  GUILD_TEXT = "guild_text",
  GUILD_VOICE = "guild_voice",
}

export type Channel = {
  id: string;
  name?: string;
  type: ChannelType;
  guild_id?: string;
  description?: string;
  created_at: string;
};
