export type Guild = {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  /** Null for most guilds; the letter icon is the common case. */
  icon_url?: string | null;
  created_at: string;
  updated_at: string;
};

export enum GuildMemberRole {
  ADMIN = "admin",
  MODERATOR = "moderator",
  MEMBER = "member",
}

export type GuildMember = {
  guild_id: string;
  user_id: string;
  status: string;
  role: GuildMemberRole;
};
