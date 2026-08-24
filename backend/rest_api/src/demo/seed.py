"""Create the demo account, and put it back the way it started.

Two entry points, both idempotent:

- `ensure_demo_data` creates anything in `data.DEMO` that is missing. It runs
  from the rest_api startup event so a deploy never needs a manual step.
- `reset_demo_state` deletes everything a visitor added and re-seeds the chat
  history. It runs on every demo login, which is what keeps one visitor's
  messages from greeting the next one.

Run it by hand against a live stack with:

    docker compose exec rest_api python -m src.demo.seed

The demo accounts are given a random password that is thrown away, so the only
way into the account is `POST /api/demo/login`. Nobody can sign in as `demo`
through the ordinary login form.
"""

import asyncio
import secrets
from datetime import timedelta

import structlog
from libs.db import (
    Channel,
    ChannelMember,
    ChannelType,
    FriendRequest,
    Friendship,
    Guild,
    GuildInvite,
    GuildMember,
    GuildMemberRole,
    GuildMemberStatus,
    Message,
    User,
    generate_id,
    generate_timestamp,
)
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.demo.data import (
    DEMO,
    DEMO_EMAIL,
    DEMO_EMAIL_DOMAIN,
    DEMO_GUILD_DESCRIPTION,
    DEMO_GUILD_NAME,
    DEMO_USERNAME,
)
from src.utils.hashing import get_password_hash

logger = structlog.get_logger()


async def _ensure_user(db: AsyncSession, username: str, email: str) -> User:
    """Get the seeded account for this email, creating it if it is missing.

    Email is the lookup key, not username: the address is on a domain nobody
    can register, whereas a username is only a display choice. If the preferred
    username is already taken by a real account, a suffix is added rather than
    failing the whole seed.
    """
    existing = await db.execute(select(User).where(User.email == email))
    user = existing.scalar_one_or_none()
    if user:
        return user

    taken = await db.execute(select(User.id).where(User.username == username))
    if taken.scalar_one_or_none():
        username = f"{username}_{secrets.token_hex(2)}"
        logger.warning("Demo username was taken, using a suffix", username=username)

    user = User(
        id=generate_id(),
        username=username,
        email=email,
        # Deliberately unusable. Nothing stores or transmits this value, so the
        # account cannot be reached through /auth/login.
        password_hash=await get_password_hash(secrets.token_urlsafe(32)),
    )
    db.add(user)
    await db.flush()
    logger.info("Created demo account", username=username)
    return user


async def _ensure_membership(db: AsyncSession, channel_id: str, user_id: str) -> None:
    existing = await db.execute(
        select(ChannelMember.id).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        return
    db.add(ChannelMember(channel_id=channel_id, user_id=user_id))


async def _ensure_friendship(db: AsyncSession, user_a: str, user_b: str) -> None:
    # `friendships` has a composite primary key, and the pair is stored in a
    # fixed order so one relationship cannot be inserted twice
    first, second = sorted([str(user_a), str(user_b)])
    existing = await db.execute(
        select(Friendship).where(
            Friendship.user_1_id == first, Friendship.user_2_id == second
        )
    )
    if existing.scalar_one_or_none():
        return
    db.add(Friendship(user_1_id=first, user_2_id=second))


async def _ensure_dm_channel(db: AsyncSession, user_a: str, user_b: str) -> Channel:
    """The DM shared by two users, created if they do not have one yet."""
    a_channels = select(ChannelMember.channel_id).where(ChannelMember.user_id == user_a)
    existing = await db.execute(
        select(Channel)
        .join(ChannelMember, ChannelMember.channel_id == Channel.id)
        .where(
            Channel.type == ChannelType.DM,
            ChannelMember.user_id == user_b,
            Channel.id.in_(a_channels),
        )
    )
    channel = existing.scalars().first()
    if channel:
        return channel

    channel = Channel(id=generate_id(), type=ChannelType.DM)
    db.add(channel)
    await db.flush()
    db.add(ChannelMember(channel_id=channel.id, user_id=user_a))
    db.add(ChannelMember(channel_id=channel.id, user_id=user_b))
    await db.flush()
    return channel


async def ensure_demo_data(db: AsyncSession) -> User:
    """Create every account, the guild, its channels and the friendships.

    Safe to call on a database that already has all of it; each piece is looked
    up before it is created. Does not touch messages, `reset_demo_state` owns
    those.
    """
    demo_user = await _ensure_user(db, DEMO_USERNAME, DEMO_EMAIL)

    companions: dict[str, User] = {}
    for definition in DEMO.companions:
        companions[definition.username] = await _ensure_user(
            db, definition.username, definition.email
        )

    # --- the guild -------------------------------------------------------
    guild_result = await db.execute(
        select(Guild).where(
            Guild.name == DEMO_GUILD_NAME, Guild.owner_id == demo_user.id
        )
    )
    guild = guild_result.scalar_one_or_none()
    if not guild:
        guild = Guild(
            id=generate_id(),
            name=DEMO_GUILD_NAME,
            description=DEMO_GUILD_DESCRIPTION,
            owner_id=demo_user.id,
        )
        db.add(guild)
        await db.flush()
        logger.info("Created demo guild", guild_id=str(guild.id))

    # The visitor is an admin so they can try creating a channel and inviting
    members = {demo_user.id: GuildMemberRole.ADMIN} | {
        user.id: GuildMemberRole.MEMBER for user in companions.values()
    }
    for user_id, role in members.items():
        existing = await db.execute(
            select(GuildMember).where(
                GuildMember.guild_id == guild.id, GuildMember.user_id == user_id
            )
        )
        if not existing.scalar_one_or_none():
            db.add(
                GuildMember(
                    guild_id=guild.id,
                    user_id=user_id,
                    role=role,
                    status=GuildMemberStatus.ACTIVE,
                )
            )
    await db.flush()

    # --- its channels ----------------------------------------------------
    for definition in DEMO.channels:
        existing = await db.execute(
            select(Channel).where(
                Channel.guild_id == guild.id, Channel.name == definition.name
            )
        )
        channel = existing.scalar_one_or_none()
        if not channel:
            channel = Channel(
                id=generate_id(),
                name=definition.name,
                type=definition.type,
                guild_id=guild.id,
                description=definition.description,
            )
            db.add(channel)
            await db.flush()

        # Membership of the channel, not of the guild, is what routes events
        for user_id in members:
            await _ensure_membership(db, channel.id, user_id)
    await db.flush()

    # --- friends and their DMs -------------------------------------------
    for definition in DEMO.companions:
        if not definition.friend:
            continue
        companion = companions[definition.username]
        await _ensure_friendship(db, demo_user.id, companion.id)
        await _ensure_dm_channel(db, demo_user.id, companion.id)
    await db.flush()

    # --- one unanswered friend request -----------------------------------
    if DEMO.pending_requester:
        requester = await _ensure_user(
            db, DEMO.pending_requester.username, DEMO.pending_requester.email
        )
        existing = await db.execute(
            select(FriendRequest).where(
                FriendRequest.from_user_id == requester.id,
                FriendRequest.to_user_id == demo_user.id,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(
                FriendRequest(
                    id=generate_id(),
                    from_user_id=requester.id,
                    to_user_id=demo_user.id,
                )
            )
    await db.flush()

    return demo_user


async def _seed_users(db: AsyncSession) -> dict[str, User]:
    """Every seeded account, keyed by username, for message authorship."""
    result = await db.execute(
        select(User).where(User.email.like(f"%@{DEMO_EMAIL_DOMAIN}"))
    )
    return {user.email.split("@")[0]: user for user in result.scalars().all()}


async def _delete_channels(db: AsyncSession, channel_ids: list[str]) -> None:
    """Drop channels and everything that points at them.

    Order matters: `messages` and `channel_members` both have a foreign key to
    `channels` with no cascade, so they go first.
    """
    if not channel_ids:
        return
    await db.execute(delete(Message).where(Message.channel_id.in_(channel_ids)))
    await db.execute(
        delete(ChannelMember).where(ChannelMember.channel_id.in_(channel_ids))
    )
    await db.execute(delete(Channel).where(Channel.id.in_(channel_ids)))


async def reset_demo_state(db: AsyncSession) -> User:
    """Return the demo account to exactly what `data.DEMO` describes.

    A visitor can do anything a real user can: send messages, create a guild,
    add a channel, send a friend request. Without this the account would
    accumulate every visitor's leftovers, and the next person would be reading
    a stranger's chat. Called on every demo login.

    Deliberately not published as realtime events. A second visitor who is
    signed in at the same moment will see a stale view until their next fetch,
    which is inherent to sharing one account and is the tradeoff taken here.
    """
    demo_user = await ensure_demo_data(db)
    users = await _seed_users(db)
    seed_user_ids = [user.id for user in users.values()]

    guild_result = await db.execute(
        select(Guild).where(
            Guild.name == DEMO_GUILD_NAME, Guild.owner_id == demo_user.id
        )
    )
    demo_guild = guild_result.scalar_one()

    # --- guilds the visitor created --------------------------------------
    stray_guilds = await db.execute(
        select(Guild.id).where(
            Guild.owner_id == demo_user.id, Guild.id != demo_guild.id
        )
    )
    for guild_id in stray_guilds.scalars().all():
        channel_ids = (
            (await db.execute(select(Channel.id).where(Channel.guild_id == guild_id)))
            .scalars()
            .all()
        )
        await _delete_channels(db, list(channel_ids))
        await db.execute(delete(GuildInvite).where(GuildInvite.guild_id == guild_id))
        await db.execute(delete(GuildMember).where(GuildMember.guild_id == guild_id))
        await db.execute(delete(Guild).where(Guild.id == guild_id))

    # --- guilds the visitor joined, and invites they were sent ------------
    await db.execute(
        delete(GuildMember).where(
            GuildMember.user_id == demo_user.id,
            GuildMember.guild_id != demo_guild.id,
        )
    )
    await db.execute(delete(GuildInvite).where(GuildInvite.user_id == demo_user.id))
    await db.execute(delete(GuildInvite).where(GuildInvite.inviter_id == demo_user.id))

    # --- channels the visitor added to the demo guild ---------------------
    keep_names = [definition.name for definition in DEMO.channels]
    stray_channels = await db.execute(
        select(Channel.id).where(
            Channel.guild_id == demo_guild.id, Channel.name.notin_(keep_names)
        )
    )
    await _delete_channels(db, list(stray_channels.scalars().all()))

    # --- DMs with anyone outside the seeded cast --------------------------
    demo_channel_ids = select(ChannelMember.channel_id).where(
        ChannelMember.user_id == demo_user.id
    )
    stray_dms = await db.execute(
        select(Channel.id)
        .join(ChannelMember, ChannelMember.channel_id == Channel.id)
        .where(
            Channel.type == ChannelType.DM,
            Channel.id.in_(demo_channel_ids),
            ChannelMember.user_id.notin_(seed_user_ids),
        )
    )
    await _delete_channels(db, list(set(stray_dms.scalars().all())))

    # --- friendships and requests outside the seeded cast -----------------
    await db.execute(
        delete(Friendship).where(
            or_(
                Friendship.user_1_id == demo_user.id,
                Friendship.user_2_id == demo_user.id,
            ),
            Friendship.user_1_id.notin_(seed_user_ids)
            | Friendship.user_2_id.notin_(seed_user_ids),
        )
    )
    await db.execute(
        delete(FriendRequest).where(
            or_(
                FriendRequest.from_user_id == demo_user.id,
                FriendRequest.to_user_id == demo_user.id,
            )
        )
    )
    await db.flush()

    # The seeded data may have just been partially removed above (a visitor who
    # left the guild, or deleted a DM), so rebuild before re-seeding messages.
    demo_user = await ensure_demo_data(db)
    await _seed_messages(db, demo_user, demo_guild, users)
    return demo_user


async def _seed_messages(
    db: AsyncSession,
    demo_user: User,
    demo_guild: Guild,
    users: dict[str, User],
) -> None:
    """Wipe every message the demo account can see, then write the scripted ones."""
    visible_channel_ids = (
        (
            await db.execute(
                select(ChannelMember.channel_id).where(
                    ChannelMember.user_id == demo_user.id
                )
            )
        )
        .scalars()
        .all()
    )
    if visible_channel_ids:
        await db.execute(
            delete(Message).where(Message.channel_id.in_(list(visible_channel_ids)))
        )

    def build(channel_id: str, scripted) -> list[Message]:
        rows = []
        for line in scripted:
            author = users.get(line.author)
            if not author:
                continue
            rows.append(
                Message(
                    id=generate_id(),
                    content=line.text,
                    sender_id=author.id,
                    channel_id=channel_id,
                    # Relative, so the history reads as recent however long ago
                    # this was deployed
                    created_at=generate_timestamp(timedelta(minutes=-line.minutes_ago)),
                )
            )
        return rows

    messages: list[Message] = []

    for name, scripted in DEMO.guild_messages.items():
        channel = await db.execute(
            select(Channel).where(
                Channel.guild_id == demo_guild.id, Channel.name == name
            )
        )
        channel = channel.scalar_one_or_none()
        if channel:
            messages.extend(build(channel.id, scripted))

    for username, scripted in DEMO.dm_messages.items():
        companion = users.get(username)
        if not companion:
            continue
        channel = await _ensure_dm_channel(db, demo_user.id, companion.id)
        messages.extend(build(channel.id, scripted))

    db.add_all(messages)
    await db.flush()
    logger.info("Reseeded demo messages", count=len(messages))


async def seed_demo(session_factory) -> None:
    """Create the demo account if missing and reset it. One transaction."""
    async with session_factory() as session:
        async with session.begin():
            await reset_demo_state(session)
    logger.info("Demo data is seeded")


if __name__ == "__main__":
    from src.database.core import AsyncSessionLocal

    asyncio.run(seed_demo(AsyncSessionLocal))
