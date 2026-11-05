"""What a client frame may become, and who may post.

Stdlib `unittest`, like event_consumer's: no database, no Redis, no config.

    cd backend/ws_gateway && python -m unittest discover -s tests

The attacks themselves are in `tests/e2e/ws_abuse_probe.py`. These pin down the
rules one field at a time, which an end-to-end test has no patience for. Every
frame here is something the UI never sends.
"""

import asyncio
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.db import MAX_ATTACHMENTS_PER_MESSAGE, MAX_MESSAGE_LENGTH  # noqa: E402
from libs.event.schema import EventType, TargetType  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from src.message.dispatcher import MessageEventDispatcher  # noqa: E402
from src.message.ingest import build_client_event, rate_limited_frame  # noqa: E402

SENDER = str(uuid4())
CHANNEL = str(uuid4())


def frame(**overrides):
    return {
        "event_type": "message",
        "receiver_id": CHANNEL,
        "text": "hello",
        **overrides,
    }


class WhatIsAccepted(unittest.TestCase):
    def test_a_plain_message(self):
        event = build_client_event(frame(), SENDER)
        self.assertEqual(event.event_type, EventType.MESSAGE)
        self.assertEqual(event.text, "hello")
        self.assertEqual(event.sender_id, SENDER)
        self.assertEqual(event.target_id, CHANNEL)
        self.assertIs(event.target_type, TargetType.CHANNEL)

    def test_target_id_works_as_well_as_receiver_id(self):
        event = build_client_event(
            {"event_type": "message", "target_id": CHANNEL, "text": "hi"}, SENDER
        )
        self.assertEqual(event.target_id, CHANNEL)

    def test_an_image_needs_no_text(self):
        image = str(uuid4())
        event = build_client_event(
            frame(text="", metadata={"attachment_ids": [image]}), SENDER
        )
        self.assertEqual(event.metadata, {"attachment_ids": [image]})

    def test_a_message_at_the_limit(self):
        text = "x" * MAX_MESSAGE_LENGTH
        self.assertEqual(build_client_event(frame(text=text), SENDER).text, text)


class WhatIsDropped(unittest.TestCase):
    def assertDropped(self, value):
        self.assertIsNone(build_client_event(value, SENDER))

    def test_every_other_event_type(self):
        for event_type in EventType:
            if event_type is not EventType.MESSAGE:
                self.assertDropped(frame(event_type=event_type.value))

    def test_a_frame_that_is_not_an_object(self):
        for value in ([], "message", 7, None, True):
            self.assertDropped(value)

    def test_a_channel_that_is_not_a_uuid(self):
        for channel in ("nope", "", None, 7, [CHANNEL]):
            self.assertDropped(frame(receiver_id=channel))

    def test_text_that_is_not_a_string(self):
        for text in (7, None, ["a"], {"a": 1}):
            self.assertDropped(frame(text=text))

    def test_nothing_to_say(self):
        for text in ("", "   ", "\n\t", "\x00"):
            self.assertDropped(frame(text=text))

    def test_over_the_length_limit(self):
        self.assertDropped(frame(text="x" * (MAX_MESSAGE_LENGTH + 1)))

    def test_a_lone_surrogate(self):
        # Cannot be encoded on the way to Postgres, so it would fail the batch
        self.assertDropped(frame(text="a\ud800b"))


class WhatIsIgnored(unittest.TestCase):
    """Fields a client may send and has no say over."""

    def test_the_server_chooses_the_id(self):
        chosen = str(uuid4())
        event = build_client_event(frame(event_id=chosen), SENDER)
        self.assertNotEqual(event.event_id, chosen)

    def test_the_server_chooses_the_time(self):
        event = build_client_event(frame(timestamp="1999-01-01T00:00:00+00:00"), SENDER)
        self.assertNotIn("1999", event.timestamp)

    def test_the_sender_is_the_socket_not_the_frame(self):
        event = build_client_event(frame(sender_id=str(uuid4())), SENDER)
        self.assertEqual(event.sender_id, SENDER)

    def test_a_message_cannot_claim_to_be_user_addressed(self):
        event = build_client_event(frame(target_type="user"), SENDER)
        self.assertIs(event.target_type, TargetType.CHANNEL)

    def test_metadata_is_only_ever_attachment_ids(self):
        event = build_client_event(
            frame(metadata={"channels_changed": True, "action": "x"}), SENDER
        )
        self.assertIsNone(event.metadata)

    def test_a_nul_is_removed_rather_than_stored(self):
        self.assertEqual(build_client_event(frame(text="a\x00b"), SENDER).text, "ab")

    def test_attachments_are_deduplicated_and_capped(self):
        ids = [str(uuid4()) for _ in range(MAX_ATTACHMENTS_PER_MESSAGE + 3)]
        event = build_client_event(
            frame(metadata={"attachment_ids": [ids[0], ids[0], "nope", *ids]}), SENDER
        )
        self.assertEqual(
            event.metadata["attachment_ids"], ids[:MAX_ATTACHMENTS_PER_MESSAGE]
        )


class RateLimitedFrame(unittest.TestCase):
    def test_it_names_the_wait(self):
        built = rate_limited_frame(SENDER, 8)
        self.assertEqual(built["metadata"]["action"], "rate_limited")
        self.assertEqual(built["metadata"]["retry_after"], 8)
        self.assertIn("8 seconds", built["text"])

    def test_one_second_is_singular(self):
        self.assertIn("1 second.", rate_limited_frame(SENDER, 1)["text"])


class FakeSession:
    """Answers the membership query with whatever rows it was built with."""

    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return self.rows


class Authorized(unittest.TestCase):
    def authorized(self, events, rows):
        return asyncio.run(
            MessageEventDispatcher().authorized(FakeSession(rows), events)
        )

    def test_a_member_is_kept_and_a_stranger_is_dropped(self):
        stranger = str(uuid4())
        member_event = build_client_event(frame(), SENDER)
        stranger_event = build_client_event(frame(), stranger)
        kept = self.authorized([member_event, stranger_event], [(CHANNEL, SENDER)])
        self.assertEqual(kept, [member_event])

    def test_membership_of_one_channel_says_nothing_about_another(self):
        # Both ids appear in the rows, but never together
        other_channel, other_user = str(uuid4()), str(uuid4())
        event = build_client_event(frame(receiver_id=other_channel), SENDER)
        rows = [(CHANNEL, SENDER), (other_channel, other_user)]
        self.assertEqual(self.authorized([event], rows), [])

    def test_the_database_returns_uuids_not_strings(self):
        from uuid import UUID

        event = build_client_event(frame(), SENDER)
        rows = [(UUID(CHANNEL), UUID(SENDER))]
        self.assertEqual(self.authorized([event], rows), [event])


class FakeSavepoint:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FlakySession:
    """Fails any insert containing the poisoned channel, like a foreign key."""

    def __init__(self, poison):
        self.poison = poison
        self.stored = []

    def begin_nested(self):
        return FakeSavepoint()

    async def execute(self, _statement, rows=None):
        if any(row["channel_id"] == self.poison for row in rows):
            raise IntegrityError("insert", {}, Exception("fk"))
        self.stored.extend(row["id"] for row in rows)


class InsertIsolation(unittest.TestCase):
    def test_one_bad_row_costs_one_message(self):
        poison = str(uuid4())
        good = [build_client_event(frame(), SENDER) for _ in range(3)]
        bad = build_client_event(frame(receiver_id=poison), SENDER)
        session = FlakySession(poison)
        kept = asyncio.run(
            MessageEventDispatcher().dispatch_events(session, [good[0], bad, *good[1:]])
        )
        self.assertEqual(kept, good)
        self.assertEqual(session.stored, [e.event_id for e in good])

    def test_a_clean_batch_is_one_statement(self):
        events = [build_client_event(frame(), SENDER) for _ in range(3)]
        session = FlakySession(str(uuid4()))
        calls = []
        original = session.execute

        async def counting(statement, rows=None):
            calls.append(rows)
            await original(statement, rows)

        session.execute = counting
        asyncio.run(MessageEventDispatcher().dispatch_events(session, events))
        self.assertEqual(len(calls), 1)

    def test_nothing_to_insert_does_not_touch_the_database(self):
        session = FlakySession(str(uuid4()))
        self.assertEqual(
            asyncio.run(MessageEventDispatcher().dispatch_events(session, [])), []
        )


if __name__ == "__main__":
    unittest.main()
