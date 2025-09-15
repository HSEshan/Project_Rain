from typing import Optional

from pydantic import BaseModel
from src.channel.models import ChannelType


class DMChannelCreate(BaseModel):
    user_id: str
    user_id2: str


class GuildChannelCreate(BaseModel):
    type: ChannelType
    name: Optional[str] = None
    guild_id: Optional[str] = None
    description: Optional[str] = None
