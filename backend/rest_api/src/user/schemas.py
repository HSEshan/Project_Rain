from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class BulkUserRequest(BaseModel):
    ids: list[str]


class UserResponse(BaseModel):
    """A user as anyone else is allowed to see them.

    **Every route that returns a `User` must declare a response model.** The ORM
    object carries `email` and `password_hash`, and FastAPI serialises whatever
    it is handed: without this, `GET /users/` returned both to any authenticated
    caller. Fixed 2026-08-25; do not remove a `response_model` from these routes.
    """

    id: str
    username: str

    model_config = {"from_attributes": True}

    # `User.id` is a SQLAlchemy UUID column, so the attribute is a `uuid.UUID`
    # and pydantic will not narrow that to `str` on its own.
    @field_validator("id", mode="before")
    @classmethod
    def _as_str(cls, value):
        return str(value)


class BulkUserResponse(BaseModel):
    users: list[UserResponse]


class FriendState(str, Enum):
    """Where the viewer and this user stand with each other."""

    SELF = "self"
    FRIENDS = "friends"
    # A request is pending; the direction is from the viewer's point of view.
    REQUEST_SENT = "request_sent"
    REQUEST_RECEIVED = "request_received"
    NONE = "none"


class MutualGuild(BaseModel):
    id: str
    name: str


class UserProfile(BaseModel):
    """What the profile card shows.

    Deliberately more than a username: a card that only echoes the name the
    caller already clicked on is not worth a request. The relationship fields
    are what let the card offer the right action (message, add friend, or
    nothing) without the client stitching together three stores and guessing.

    Still no email. Who someone is to *you* is shareable; their login is not.
    """

    id: str
    username: str
    created_at: datetime
    friend_state: FriendState
    # An existing DM with this user, so the card can offer "Message" rather than
    # creating a second DM channel with the same person.
    dm_channel_id: Optional[str] = None
    mutual_guilds: list[MutualGuild] = []

    model_config = {"from_attributes": True}
