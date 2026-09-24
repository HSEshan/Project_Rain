import re
from datetime import datetime
from enum import Enum
from typing import Optional

from libs.db import BIO_MAX_LENGTH
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
    # Null means nobody has written one, which the card treats differently from
    # an empty string: one gets a prompt, the other could not exist.
    bio: Optional[str] = None
    created_at: datetime
    friend_state: FriendState
    # An existing DM with this user, so the card can offer "Message" rather than
    # creating a second DM channel with the same person.
    dm_channel_id: Optional[str] = None
    mutual_guilds: list[MutualGuild] = []

    model_config = {"from_attributes": True}


# Anything that is not a newline and not printable. A bio is typed into a
# textarea, so newlines are legitimate; a NUL, a bell, or one of the
# bidirectional-override characters is not, and those are exactly the ones that
# make text render as something other than what was typed.
_CONTROL_CHARACTERS = re.compile(
    r"[\x00-\x08\x0b-\x1f\x7f‎‏‪-‮]"
)
_BLANK_LINE_RUNS = re.compile(r"\n{3,}")


class UserUpdate(BaseModel):
    """What a user may change about themselves.

    One field today, and the shape is chosen for the second one: `PATCH` means
    "change what I named", so the service reads `model_fields_set` rather than
    treating a missing key as `null`. Without that, a later request that only
    sets an avatar would silently erase a bio.

    **The bio is plain text and is never HTML.** It is written by one person and
    rendered to others, which is the definition of untrusted input; React
    escapes it on the way out, and nothing here should ever hand it to
    `dangerouslySetInnerHTML`. Normalising is not sanitising and does not
    replace that.
    """

    bio: Optional[str] = None

    @field_validator("bio")
    @classmethod
    def clean_bio(cls, bio: Optional[str]) -> Optional[str]:
        if bio is None:
            return None

        bio = _CONTROL_CHARACTERS.sub("", bio)
        # Whitespace at both ends of every line, then runs of blank lines. A bio
        # renders with `whitespace-pre-line`, so ten blank lines are ten blank
        # lines on everyone else's screen: two is a paragraph break, more is
        # someone taking up room in a layout they share with other people.
        #
        # Both ends rather than just the trailing one, which is what this did
        # first: stripping one and not the other means a pasted, indented line
        # comes out half-tidied, and there is no formatting worth preserving in
        # 190 characters that leading spaces express.
        bio = "\n".join(line.strip() for line in bio.split("\n"))
        bio = _BLANK_LINE_RUNS.sub("\n\n", bio).strip()

        # Measured after normalising, so trailing whitespace cannot fail a bio
        # that fits. One sentence a person can act on, like the signup rules.
        if len(bio) > BIO_MAX_LENGTH:
            raise ValueError(
                f"Bio must be {BIO_MAX_LENGTH} characters or fewer "
                f"(that one is {len(bio)})"
            )

        # An empty bio is the absence of one. Storing "" would hand the card a
        # value to render and nothing to render, and would make "cleared it" and
        # "never wrote one" two states that look identical and compare unequal.
        return bio or None
