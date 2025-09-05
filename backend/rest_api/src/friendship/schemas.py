from pydantic import BaseModel, ConfigDict
from src.channel.models import Channel
from src.friendship.models import Friendship


class FriendRequestCreate(BaseModel):
    from_user_id: str
    to_user_id: str


class FriendRequestAccept(BaseModel):
    friendship: Friendship
    dm_channel: Channel

    model_config = ConfigDict(arbitrary_types_allowed=True)
