"""The canonical shape of the demo account.

One place describes everything a visitor sees when they click "Try the demo":
the accounts, the guild, its channels, the friendships, and the seeded chat
history. `seed.py` makes the database match this, and makes it match again on
every demo login.

Everything here is namespaced under `demo_` usernames and the `DEMO_EMAIL_DOMAIN`
so it can never collide with a real account, and so the reset can find its own
rows without guessing.
"""

from dataclasses import dataclass, field

from libs.db import ChannelType

# Emails are the stable identity for seeded accounts: usernames are what a
# visitor sees and could in principle be taken, an address on this domain
# cannot be registered through the normal flow.
DEMO_EMAIL_DOMAIN = "rain.demo"

# The account the visitor is signed in as.
DEMO_USERNAME = "demo"
DEMO_EMAIL = f"{DEMO_USERNAME}@{DEMO_EMAIL_DOMAIN}"

DEMO_GUILD_NAME = "Rain Demo Server"
DEMO_GUILD_DESCRIPTION = "A tour of guild text and voice channels."


@dataclass(frozen=True)
class DemoUser:
    username: str
    # Whether this account is friends with `demo` and has a DM with them
    friend: bool = True

    @property
    def email(self) -> str:
        return f"{self.username}@{DEMO_EMAIL_DOMAIN}"


@dataclass(frozen=True)
class DemoChannel:
    name: str
    type: ChannelType
    description: str | None = None


@dataclass(frozen=True)
class DemoMessage:
    """One seeded message.

    `minutes_ago` is relative so the history always looks recent rather than
    frozen on the day the demo was first deployed, and the spread is wide
    enough that the day separators and the author grouping in `MessageView`
    both have something to render.
    """

    author: str
    text: str
    minutes_ago: int


@dataclass(frozen=True)
class DemoDefinition:
    companions: list[DemoUser] = field(default_factory=list)
    channels: list[DemoChannel] = field(default_factory=list)
    # channel name -> messages
    guild_messages: dict[str, list[DemoMessage]] = field(default_factory=dict)
    # companion username -> messages in that DM
    dm_messages: dict[str, list[DemoMessage]] = field(default_factory=dict)
    # Someone who has asked to be friends but has not been accepted, so the
    # Friends page and the sidebar badge are not empty on arrival.
    pending_requester: DemoUser | None = None


DEMO = DemoDefinition(
    companions=[
        DemoUser("demo_ada"),
        DemoUser("demo_grace"),
        DemoUser("demo_linus"),
    ],
    pending_requester=DemoUser("demo_kai", friend=False),
    channels=[
        DemoChannel("welcome", ChannelType.GUILD_TEXT, "Start here"),
        DemoChannel("general", ChannelType.GUILD_TEXT, "Anything goes"),
        DemoChannel("engineering", ChannelType.GUILD_TEXT, "How it was built"),
        DemoChannel("General Voice", ChannelType.GUILD_VOICE),
        DemoChannel("Lounge", ChannelType.GUILD_VOICE),
    ],
    guild_messages={
        "welcome": [
            DemoMessage(
                "demo_ada",
                "Welcome to the demo server. Everything here is real: the "
                "messages go over a websocket, get written to Postgres, and "
                "come back through Redis and gRPC.",
                2890,
            ),
            DemoMessage(
                "demo_ada",
                "Try the voice channels in the sidebar. Those do not use this "
                "pipeline at all, the audio goes straight to the SFU.",
                2884,
            ),
            DemoMessage(
                "demo_grace",
                "Open this page in a second tab and send something. It arrives "
                "in both, which is the multi-socket handling doing its job.",
                1450,
            ),
            DemoMessage(
                "demo_linus",
                "Heads up: messages on the demo account are cleared "
                "automatically, so nothing you type here sticks around.",
                180,
            ),
        ],
        "general": [
            DemoMessage("demo_grace", "Anyone around?", 320),
            DemoMessage("demo_linus", "Here. What is up?", 316),
            DemoMessage(
                "demo_grace",
                "Just checking the guild fan-out still works after the last "
                "deploy. Looks fine.",
                315,
            ),
            DemoMessage("demo_ada", "It does. I watched the consumer logs.", 44),
        ],
        "engineering": [
            DemoMessage(
                "demo_ada",
                "Events are sharded across sixteen Redis streams, hashed on "
                "the receiver id, so everything for one channel stays ordered.",
                1500,
            ),
            DemoMessage(
                "demo_linus",
                "And a lease manager hands those shards out to whichever "
                "consumers are alive, so they can be restarted freely.",
                1496,
            ),
            DemoMessage(
                "demo_ada",
                "Voice is a self-hosted LiveKit SFU. Only presence rides the "
                "event pipeline, never the audio.",
                60,
            ),
        ],
    },
    dm_messages={
        "demo_ada": [
            DemoMessage("demo_ada", "Hey, glad you made it in.", 1400),
            DemoMessage(
                "demo_ada",
                "This is a direct message. Same protocol as a guild channel, "
                "the only difference is the channel type.",
                1398,
            ),
            DemoMessage("demo", "Makes sense. Having a look around now.", 1390),
            DemoMessage(
                "demo_ada",
                "Take your time. The guild in the sidebar has the voice "
                "channels if you want to hear the SFU working.",
                55,
            ),
        ],
        "demo_grace": [
            DemoMessage("demo_grace", "Ping me if anything looks broken.", 900),
            DemoMessage("demo", "Will do.", 880),
        ],
        "demo_linus": [
            DemoMessage(
                "demo_linus",
                "The friend request in your Friends tab is a real pending "
                "request, you can accept or decline it.",
                240,
            ),
        ],
    },
)


def all_demo_usernames() -> list[str]:
    """Every seeded account, the visitor's included."""
    names = [DEMO_USERNAME] + [companion.username for companion in DEMO.companions]
    if DEMO.pending_requester:
        names.append(DEMO.pending_requester.username)
    return names
