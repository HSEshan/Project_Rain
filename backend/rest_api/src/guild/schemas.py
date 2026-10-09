from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class GuildCreate(BaseModel):
    name: str
    description: str


class GuildUpdate(BaseModel):
    id: str
    name: str
    description: str


class GuildMemberInvite(BaseModel):
    """Who to invite, by id or by username.

    The id is the canonical form; the username exists because that is what a
    person types. Friend requests already work by username, so requiring the
    client to resolve one itself would be the odd case, not this.
    """

    user_id: Optional[str] = None
    username: Optional[str] = None

    @model_validator(mode="after")
    def exactly_one_identifier(self):
        if bool(self.user_id) == bool(self.username):
            raise ValueError("Provide exactly one of user_id or username")
        return self


class GuildInviteSummary(BaseModel):
    """A pending invite, as the invited user needs to see it.

    Carries the guild name so the list does not need a second round trip, and
    the guild id because accepting is scoped to the guild's route. The inviter
    is optional: invites created before the column existed have none, and the
    inviter may have deleted their account since.
    """

    invite_id: str
    guild_id: str
    guild_name: str
    inviter_id: Optional[str] = None
    inviter_username: Optional[str] = None
    expires_at: datetime


class GuildMemberRemove(BaseModel):
    guild_id: str
    member_id: str


class GuildResponse(BaseModel):
    """A guild as its members see it.

    Added with the icon (Phase 19). These routes used to return the ORM row
    with no response model, which was harmless only while every column was
    public; a response model is the allowlist, and the icon added the first
    column (`icon_key`) that should not leave the server as-is.
    """

    id: str
    name: str
    description: str
    owner_id: Optional[str] = None
    icon_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "owner_id", mode="before")
    @classmethod
    def _as_str(cls, value):
        return str(value) if value is not None else None
