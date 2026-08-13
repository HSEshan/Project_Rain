from pydantic import BaseModel


class GuildCreate(BaseModel):
    name: str
    description: str


class GuildUpdate(BaseModel):
    id: str
    name: str
    description: str


class GuildMemberInvite(BaseModel):
    user_id: str


class GuildMemberRemove(BaseModel):
    guild_id: str
    member_id: str
