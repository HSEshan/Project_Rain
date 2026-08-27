from datetime import datetime
from typing import Optional

from libs.db import MAX_GROUP_DM_MEMBERS, ChannelType
from pydantic import BaseModel, Field, field_validator


class DMChannelCreate(BaseModel):
    user_id: str
    user_id2: str


class GuildChannelCreate(BaseModel):
    type: ChannelType
    name: str
    description: Optional[str] = None


class GroupDMCreate(BaseModel):
    """Everyone except the creator, who is added implicitly.

    At least two others, so a group DM is never just a DM wearing a different
    type. One other person is already a supported conversation and it has its
    own channel type, its own creation path and no member list to manage.
    """

    user_ids: list[str] = Field(min_length=2, max_length=MAX_GROUP_DM_MEMBERS - 1)
    name: Optional[str] = Field(default=None, max_length=80)

    @field_validator("user_ids")
    @classmethod
    def no_duplicates(cls, user_ids: list[str]) -> list[str]:
        if len(set(user_ids)) != len(user_ids):
            raise ValueError("Duplicate user in the group")
        return user_ids


class GroupDMMemberAdd(BaseModel):
    user_id: str


class GroupDMUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)


class ChannelResponse(BaseModel):
    """A channel as the client sees it.

    Declared rather than returning the ORM row, so that adding a column does
    not silently widen the API. `Channel` has nothing secret on it today, which
    is exactly the assumption that was wrong about `User`.
    """

    id: str
    name: Optional[str] = None
    type: ChannelType
    guild_id: Optional[str] = None
    description: Optional[str] = None
    owner_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    # UUID columns come back as `uuid.UUID`, which pydantic will not narrow to
    # `str` by itself. Same reason `UserResponse` carries one.
    @field_validator("id", "guild_id", "owner_id", mode="before")
    @classmethod
    def _as_str(cls, value):
        return str(value) if value is not None else None


class ChannelMemberResponse(BaseModel):
    user_id: str
    username: str
    is_owner: bool


class ChannelMembers(BaseModel):
    channel_id: str
    members: list[ChannelMemberResponse]
