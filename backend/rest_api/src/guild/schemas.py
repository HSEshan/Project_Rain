from pydantic import BaseModel
from src.guild.models import GuildMemberStatus


class GuildCreate(BaseModel):
    name: str
    description: str


class GuildUpdate(BaseModel):
    id: str
    name: str
    description: str


class GuildMemberCreate(BaseModel):
    guild_id: str
    user_id: str
    status: GuildMemberStatus


class GuildMemberUpdate(BaseModel):
    status: GuildMemberStatus


class GuildMemberInvite(BaseModel):
    guild_id: str
    user_id: str
