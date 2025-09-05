from typing import Optional

from pydantic import BaseModel
from src.channel.models import ChannelType


class DMChannelCreate(BaseModel):
    user_id: str
    user_id2: str


class DMChannelResponse(BaseModel):
    payload: dict[str, dict] = {}

    def push(self, channel_id: str, participant: dict):
        if channel_id not in self.payload:
            self.payload[channel_id] = {
                "channel_id": channel_id,
                "participants": [],
            }
        self.payload[channel_id]["participants"].append(participant)

    def to_list(self):
        return list(self.payload.values())


class GuildChannelCreate(BaseModel):
    type: ChannelType
    name: Optional[str] = None
    guild_id: Optional[str] = None
    description: Optional[str] = None
