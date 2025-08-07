from pydantic import BaseModel
from src.guild.models import GuildMemberStatus


class GuildCreate(BaseModel):
    name: str
    description: str


class GuildUpdate(BaseModel):
    id: str
    name: str
    description: str


class GuildMemberInvite(BaseModel):
    guild_id: str
    user_id: str


class GuildMemberRemove(BaseModel):
    guild_id: str
    member_id: str
