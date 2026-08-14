from typing import Optional

from pydantic import BaseModel
from libs.db import ChannelType


class DMChannelCreate(BaseModel):
    user_id: str
    user_id2: str


class GuildChannelCreate(BaseModel):
    type: ChannelType
    name: str
    description: Optional[str] = None
