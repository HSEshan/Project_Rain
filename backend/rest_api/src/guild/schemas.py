from datetime import datetime
from typing import Optional

from libs.db import GuildMemberRole, GuildMemberStatus
from pydantic import BaseModel, Field, field_validator, model_validator

GUILD_NAME_MAX_LENGTH = 100
# Well under what the index on the column can hold: a btree entry past about
# 2.7KB is a database error, and this should be a readable 422 long before that.
GUILD_DESCRIPTION_MAX_LENGTH = 300


def _clean_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("A guild needs a name")
    if len(value) > GUILD_NAME_MAX_LENGTH:
        raise ValueError(
            f"Guild names can be up to {GUILD_NAME_MAX_LENGTH} characters"
        )
    return value


def _clean_description(value: str) -> str:
    value = value.strip()
    if len(value) > GUILD_DESCRIPTION_MAX_LENGTH:
        raise ValueError(
            f"Guild descriptions can be up to {GUILD_DESCRIPTION_MAX_LENGTH} "
            "characters"
        )
    return value


class GuildCreate(BaseModel):
    name: str
    description: str

    _name = field_validator("name")(_clean_name)
    _description = field_validator("description")(_clean_description)


class GuildUpdate(BaseModel):
    """What an admin may change. Only fields present in the body are applied.

    Read through `model_fields_set`, as `PATCH /users/me` does: a missing field
    parses to None, and that must not read as "clear it".
    """

    name: Optional[str] = None
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: Optional[str]) -> str:
        # Present and null is a request for a guild with no name, which there
        # is no such thing as.
        return _clean_name(value or "")

    @field_validator("description")
    @classmethod
    def _description(cls, value: Optional[str]) -> str:
        return _clean_description(value or "")


class GuildMemberRoleUpdate(BaseModel):
    role: GuildMemberRole


class GuildBanResponse(BaseModel):
    user_id: str
    username: str
    created_at: datetime


class GuildTransfer(BaseModel):
    user_id: str


class InviteLinkCreate(BaseModel):
    """Both optional: a link with neither never expires and has no use limit."""

    expires_in_hours: Optional[int] = Field(default=None, ge=1, le=24 * 30)
    max_uses: Optional[int] = Field(default=None, ge=1, le=1000)


class InviteLinkResponse(BaseModel):
    code: str
    guild_id: str
    creator_id: Optional[str] = None
    max_uses: Optional[int] = None
    uses: int
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("guild_id", "creator_id", mode="before")
    @classmethod
    def _as_str(cls, value):
        return str(value) if value is not None else None


class InviteLinkPreview(BaseModel):
    guild_name: str
    guild_description: str
    icon_url: Optional[str] = None
    member_count: int


class InviteLinkAccepted(BaseModel):
    guild_id: str
    already_member: bool


class GuildMemberResponse(BaseModel):
    """A member row. These routes returned the ORM object with no model."""

    guild_id: str
    user_id: str
    status: GuildMemberStatus
    role: GuildMemberRole

    model_config = {"from_attributes": True}

    @field_validator("guild_id", "user_id", mode="before")
    @classmethod
    def _as_str(cls, value):
        return str(value)


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


class GuildInviteResponse(BaseModel):
    invite_id: str
    guild_id: str
    user_id: str
    inviter_id: Optional[str] = None
    expires_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("invite_id", "guild_id", "user_id", "inviter_id", mode="before")
    @classmethod
    def _as_str(cls, value):
        return str(value) if value is not None else None


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
