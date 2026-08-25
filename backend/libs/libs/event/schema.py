from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_id() -> str:
    return str(uuid4())


class EventType(str, Enum):
    MESSAGE = "message"
    CALL = "call"
    NOTIFICATION = "notification"
    FRIEND_REQUEST = "friend_request"
    # Someone joined or left a voice channel. Channel-addressed: `receiver_id`
    # is the voice channel, so it fans out to its members exactly like a
    # message. The audio itself never touches this pipeline — that is the SFU's
    # job (see AGENTS.md, "Voice / SFU").
    VOICE_STATE = "voice_state"

    @classmethod
    def is_user_addressed(cls, event_type: "EventType | str") -> bool:
        """Whether `receiver_id` holds a user id rather than a channel id.

        Delivery differs by addressing: user-addressed events resolve through
        `user:{id}:grpc_endpoint`, channel-addressed ones through
        `channel:{id}:grpc_endpoints`. Keep this the only place that knows.
        """
        return cls(event_type) in USER_ADDRESSED_EVENT_TYPES


USER_ADDRESSED_EVENT_TYPES = frozenset(
    {EventType.NOTIFICATION, EventType.FRIEND_REQUEST}
)


class TargetType(str, Enum):
    """What kind of thing an event is addressed to.

    This is the field `receiver_id` never had. `receiver_id` is a pun: a channel
    id for `message` and `voice_state`, a user id for `notification` and
    `friend_request`, with nothing on the wire saying which. Reading a raw entry
    out of `stream_shard:7` told you nothing without also holding this module.

    Delivery still differs the same way it always did: USER resolves through
    `user:{id}:grpc_endpoint`, CHANNEL through `channel:{id}:grpc_endpoints`.
    The difference is that the event now says so itself.

    Adding a third member (GUILD is the likely one) is the point of the exercise:
    a guild-wide event is neither channel- nor single-user-addressed, and today
    it has to be faked by publishing one user-addressed event per member.
    """

    USER = "user"
    CHANNEL = "channel"


def target_type_for(event_type: "EventType | str") -> TargetType:
    """The addressing an event type implies, for events that predate the field.

    This is the old `is_user_addressed` rule expressed as the new enum, and it
    is only used as a *fallback* when an event arrives without `target_type`.
    Once every producer sets the field explicitly this can go, and with it the
    coupling between what an event is and who it reaches.
    """
    return (
        TargetType.USER
        if EventType.is_user_addressed(event_type)
        else TargetType.CHANNEL
    )


class EventAction(str, Enum):
    """Values for `Event.metadata["action"]`.

    User-addressed events all look alike on the wire, so the action tells the
    gateway and the client what actually happened.
    """

    FRIEND_REQUEST_RECEIVED = "friend_request_received"
    FRIEND_REQUEST_ACCEPTED = "friend_request_accepted"
    GUILD_INVITE_RECEIVED = "guild_invite_received"
    # An invite this user was holding is gone — declined here or in another tab.
    # Not a membership change, so it does not carry CHANNELS_CHANGED_FLAG.
    GUILD_INVITE_REMOVED = "guild_invite_removed"
    # Nothing to show the user beyond "your channels changed"
    CHANNELS_CHANGED = "channels_changed"
    VOICE_JOINED = "voice_joined"
    VOICE_LEFT = "voice_left"


# Metadata flag, set alongside any action that changed the recipient's channel
# membership. The gateway re-reads its mapping and the client refetches; the
# action says *what* happened, this says *what the receiver must reload*.
CHANNELS_CHANGED_FLAG = "channels_changed"


class Event(BaseModel):
    """One thing that happened, on its way to whoever needs to hear about it.

    **Addressing is in transition.** `receiver_id` is the original field and is
    still written and read everywhere, so nothing breaks mid-deploy;
    `target_type`/`target_id` are the replacement, and every consumer prefers
    them. The two are kept in lockstep by `_fill_target`, so a producer can set
    either pair and a consumer can read either pair.

    This is the *expand* half of an expand-and-contract migration. The contract
    half, deleting `receiver_id`, waits until nothing in flight still speaks the
    old shape: no entry left in a stream shard, and no browser still running
    JavaScript from before the deploy. See devnotes.md, Appendix A1.
    """

    event_id: str = Field(default_factory=generate_id)
    event_type: EventType
    sender_id: str
    # Deprecated, kept for wire compatibility. Read `target_id` instead.
    receiver_id: str = ""
    # Who this is for, and what kind of thing that is. Optional on input only so
    # that an event from before the migration still validates.
    target_type: Optional[TargetType] = None
    target_id: str = ""
    text: str
    metadata: Optional[dict] = None
    timestamp: str = Field(default_factory=get_timestamp)

    @model_validator(mode="after")
    def _fill_target(self) -> "Event":
        """Make the old and new addressing agree, whichever side was supplied.

        Three cases, and all three have to work at once during the migration:

        - Old producer, new field missing: copy `receiver_id` across and infer
          the type from the event type, the rule that has always applied.
        - New producer, old field missing: copy `target_id` back so a consumer
          that has not been redeployed yet still routes.
        - Both supplied and disagreeing: trust `target_id`, because it is the
          one the producer stated rather than the one something inferred.
        """
        if not self.target_id and self.receiver_id:
            object.__setattr__(self, "target_id", self.receiver_id)
        if not self.receiver_id and self.target_id:
            object.__setattr__(self, "receiver_id", self.target_id)
        if not self.target_id:
            raise ValueError("Event needs a target_id (or a legacy receiver_id)")
        if self.target_type is None:
            object.__setattr__(
                self, "target_type", target_type_for(self.event_type)
            )
        return self

    @field_validator("sender_id", "receiver_id", "target_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        # Empty is allowed here and resolved by `_fill_target`; only a value
        # that was actually supplied has to look like an id.
        if not v:
            return v
        try:
            UUID(v, version=4)
        except ValueError:
            raise ValueError(f"Invalid UUID: {v}")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except Exception:
            raise ValueError(f"Invalid ISO8601 timestamp: {v}")
        return v

    @property
    def channel_id(self) -> str:
        """The target, asserting it is a channel.

        Persistence and channel fan-out call this instead of reading the raw id,
        so routing a user-addressed event into a channel path fails loudly
        rather than writing a message row whose `channel_id` is a user id.
        """
        if self.target_type is not TargetType.CHANNEL:
            raise ValueError(
                f"Event {self.event_id} is addressed to {self.target_type}, not a channel"
            )
        return self.target_id

    @property
    def user_id(self) -> str:
        """The target, asserting it is a user."""
        if self.target_type is not TargetType.USER:
            raise ValueError(
                f"Event {self.event_id} is addressed to {self.target_type}, not a user"
            )
        return self.target_id
