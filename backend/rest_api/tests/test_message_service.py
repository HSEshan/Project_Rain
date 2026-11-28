"""Reading, editing and deleting messages: whose they are and who outranks whom.

Editing is the author's alone. Deleting someone else's needs `MANAGE_MESSAGES`
over them in a guild, and is never possible in a DM. Anyone outside the channel
is told the message does not exist.
"""

import pytest
from libs.db import Attachment, ChannelType, GuildMemberRole, Message, generate_id
from sqlalchemy import select
from src.message.schemas import MessageEdit
from src.message.service import MessageService
from src.utils.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from tests.service_db import run, side_effects, world  # noqa: F401


async def post(w, channel_id, sender, content="hello", image_key=None) -> str:
    message_id = generate_id()
    async with w.session() as db:
        db.add(
            Message(id=message_id, content=content, sender_id=sender.id, channel_id=channel_id)
        )
        await db.flush()
        if image_key:
            db.add(
                Attachment(
                    uploader_id=sender.id,
                    message_id=message_id,
                    key=image_key,
                    content_type="image/webp",
                    size_bytes=1,
                    width=1,
                    height=1,
                )
            )
        await db.commit()
    return message_id


async def exists(w, message_id) -> bool:
    return await w.scalar(select(Message.id).where(Message.id == message_id)) is not None


async def guild_text(w):
    names = ("owner", "admin", "mod", "mem", "mem2", "out")
    p = {n: await w.user(n) for n in names}
    guild_id = await w.guild(p["owner"])
    await w.member(guild_id, p["admin"], GuildMemberRole.ADMIN)
    await w.member(guild_id, p["mod"], GuildMemberRole.MODERATOR)
    await w.member(guild_id, p["mem"])
    await w.member(guild_id, p["mem2"])
    text = next(
        str(c.id) for c in await w.guild_channels(guild_id) if c.type == ChannelType.GUILD_TEXT
    )
    return guild_id, text, p


def test_history_is_for_members_only(side_effects):
    async def scenario():
        async with world() as w:
            _, text, p = await guild_text(w)
            await post(w, text, p["mem"])
            with pytest.raises(NotFoundException):
                await w.call(MessageService, "get_messages_by_channel_id", p["out"], text)
            history = await w.call(MessageService, "get_messages_by_channel_id", p["mem2"], text)
            assert [m.content for m in history] == ["hello"]

    run(scenario())


@pytest.mark.parametrize("editor", ["mem2", "mod", "admin", "owner"])
def test_nobody_edits_someone_elses_message(side_effects, editor):
    async def scenario():
        async with world() as w:
            _, text, p = await guild_text(w)
            message_id = await post(w, text, p["mem"])
            with pytest.raises(ForbiddenException):
                await w.call(
                    MessageService, "edit_message", p[editor], message_id, MessageEdit(content="put words")
                )
            row = await w.scalar(select(Message.content).where(Message.id == message_id))
            assert row == "hello"

    run(scenario())


def test_a_non_member_is_told_the_message_does_not_exist(side_effects):
    async def scenario():
        async with world() as w:
            _, text, p = await guild_text(w)
            message_id = await post(w, text, p["mem"])
            for method, args in (
                ("edit_message", (MessageEdit(content="x"),)),
                ("delete_message", ()),
            ):
                with pytest.raises(NotFoundException) as refused:
                    await w.call(MessageService, method, p["out"], message_id, *args)
                with pytest.raises(NotFoundException) as missing:
                    await w.call(MessageService, method, p["out"], generate_id(), *args)
                assert refused.value.status_code == missing.value.status_code
            assert await exists(w, message_id)

    run(scenario())


def test_the_author_edits_and_the_edit_is_stamped_and_published(side_effects):
    async def scenario():
        async with world() as w:
            _, text, p = await guild_text(w)
            message_id = await post(w, text, p["mem"])
            response = await w.call(
                MessageService, "edit_message", p["mem"], message_id, MessageEdit(content="fixed")
            )
            assert response.content == "fixed"
            assert response.edited_at is not None
            assert side_effects.events and side_effects.events[-1].metadata["message_id"] == message_id

    run(scenario())


def test_an_edit_cannot_empty_a_text_message_but_can_strip_a_caption(side_effects):
    async def scenario():
        async with world() as w:
            _, text, p = await guild_text(w)
            plain = await post(w, text, p["mem"])
            with pytest.raises(BadRequestException):
                await w.call(MessageService, "edit_message", p["mem"], plain, MessageEdit(content="   "))
            captioned = await post(w, text, p["mem"], "look", image_key="k/1.webp")
            response = await w.call(
                MessageService, "edit_message", p["mem"], captioned, MessageEdit(content="")
            )
            assert response.content == "" and len(response.attachments) == 1

    run(scenario())


@pytest.mark.parametrize(
    "author, deleter, allowed",
    [
        ("mem", "mem", True),  # your own, whatever your role
        ("mem", "mem2", False),  # no MANAGE_MESSAGES
        ("mem", "mod", True),
        ("mod", "mod2", False),  # equals
        ("admin", "mod", False),
        ("owner", "admin", False),  # the owner's row says ADMIN
        ("admin", "owner", True),
    ],
)
def test_deleting_someone_elses_guild_message_follows_rank(side_effects, author, deleter, allowed):
    async def scenario():
        async with world() as w:
            guild_id, text, p = await guild_text(w)
            p["mod2"] = await w.user("mod2")
            await w.member(guild_id, p["mod2"], GuildMemberRole.MODERATOR)
            message_id = await post(w, text, p[author])
            call = w.call(MessageService, "delete_message", p[deleter], message_id)
            if allowed:
                await call
            else:
                with pytest.raises(ForbiddenException):
                    await call
            assert await exists(w, message_id) is not allowed

    run(scenario())


def test_a_departed_authors_messages_can_be_tidied_by_a_moderator(side_effects):
    async def scenario():
        async with world() as w:
            guild_id, text, p = await guild_text(w)
            message_id = await post(w, text, p["admin"])
            from src.guild.service import GuildService

            await w.call(GuildService, "leave_guild", p["admin"], guild_id)
            await w.call(MessageService, "delete_message", p["mod"], message_id)
            assert not await exists(w, message_id)

    run(scenario())


def test_deleting_takes_the_images_with_it(side_effects):
    async def scenario():
        async with world() as w:
            _, text, p = await guild_text(w)
            message_id = await post(w, text, p["mem"], image_key="attachments/a.webp")
            await w.call(MessageService, "delete_message", p["mod"], message_id)
            assert side_effects.deleted_keys == ["attachments/a.webp"]
            assert await w.scalars(select(Attachment.id)) == []

    run(scenario())


@pytest.mark.parametrize("kind", [ChannelType.DM, ChannelType.GROUP_DM])
def test_in_a_dm_only_the_author_deletes(side_effects, kind):
    async def scenario():
        async with world() as w:
            a, b, c = [await w.user(n) for n in "abc"]
            members = (a, b, c) if kind == ChannelType.GROUP_DM else (a, b)
            channel_id = await w.channel(kind, *members)
            message_id = await post(w, channel_id, b)
            # `a` owns the group DM, which still grants nothing over b's words
            with pytest.raises(ForbiddenException):
                await w.call(MessageService, "delete_message", a, message_id)
            await w.call(MessageService, "delete_message", b, message_id)
            assert not await exists(w, message_id)

    run(scenario())
