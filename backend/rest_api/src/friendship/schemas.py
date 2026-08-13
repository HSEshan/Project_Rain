from pydantic import BaseModel


class FriendRequestCreate(BaseModel):
    from_user_id: str
    to_username: str


class FriendRequestAccept(BaseModel):
    friend_id: str
    dm_channel_id: str
