from pydantic import BaseModel


class FriendRequestCreate(BaseModel):
    from_user_id: str
    to_username: str


class FriendRequestAccept(BaseModel):
    friendship: dict
    dm_channel: dict
