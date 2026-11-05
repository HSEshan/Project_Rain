from datetime import datetime

from pydantic import BaseModel, field_validator


class FriendRequestCreate(BaseModel):
    from_user_id: str
    to_username: str


class FriendRequestResponse(BaseModel):
    id: str
    from_user_id: str
    to_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "from_user_id", "to_user_id", mode="before")
    @classmethod
    def _as_str(cls, value):
        return str(value)


class FriendRequestAccept(BaseModel):
    friend_id: str
    dm_channel_id: str
