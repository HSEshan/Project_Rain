"""The addressing migration: `receiver_id` and `target_type`/`target_id`.

Recreates the Phase 10/11 harness (2026-08-24), lost with a session scratch
directory. The expand phase is deployed and both shapes are meant to coexist, so
every pairing has to work: a legacy producer read by a new consumer, a new
producer read by a consumer that only knows `receiver_id`, and a stream entry
written before the deploy passing through every codec path. The contract phase
deletes `receiver_id`; these tests are what say when that is safe to try, and
the legacy cases are the ones that will be deleted with it.

    cd backend/libs && python -m unittest discover -s tests
"""

import json
import unittest
from uuid import uuid4

from libs.event import event_pb2
from libs.event.codec import EventCodec
from libs.event.schema import (
    USER_ADDRESSED_EVENT_TYPES,
    Event,
    EventType,
    TargetType,
    target_type_for,
)

SENDER = str(uuid4())
CHANNEL = str(uuid4())
USER = str(uuid4())


def legacy_stream_entry(event_type: EventType, receiver_id: str) -> dict[str, str]:
    """A stream entry as written before the expand deploy: no target fields."""
    return {
        "event_id": str(uuid4()),
        "event_type": event_type.value,
        "sender_id": SENDER,
        "receiver_id": receiver_id,
        "text": "hello",
        "metadata": json.dumps({"action": "friend_request_received"}),
        "timestamp": "2026-08-23T12:00:00+00:00",
    }


class LegacyProducer(unittest.TestCase):
    """Something that still sets only `receiver_id`."""

    def test_a_message_is_inferred_to_be_channel_addressed(self):
        event = Event(
            event_type=EventType.MESSAGE, sender_id=SENDER, receiver_id=CHANNEL, text="hi"
        )
        self.assertEqual(event.target_type, TargetType.CHANNEL)
        self.assertEqual(event.target_id, CHANNEL)
        self.assertEqual(event.channel_id, CHANNEL)

    def test_a_notification_is_inferred_to_be_user_addressed(self):
        event = Event(
            event_type=EventType.NOTIFICATION, sender_id=SENDER, receiver_id=USER, text=""
        )
        self.assertEqual(event.target_type, TargetType.USER)
        self.assertEqual(event.user_id, USER)

    def test_every_event_type_has_an_inferred_addressing(self):
        for event_type in EventType:
            expected = (
                TargetType.USER
                if event_type in USER_ADDRESSED_EVENT_TYPES
                else TargetType.CHANNEL
            )
            with self.subTest(event_type=event_type):
                self.assertEqual(target_type_for(event_type), expected)


class NewProducer(unittest.TestCase):
    """Something that sets only the new pair, as the web client now does."""

    def test_receiver_id_is_copied_back_for_old_consumers(self):
        event = Event(
            event_type=EventType.MESSAGE,
            sender_id=SENDER,
            target_type=TargetType.CHANNEL,
            target_id=CHANNEL,
            text="hi",
        )
        self.assertEqual(event.receiver_id, CHANNEL)

    def test_its_redis_entry_still_carries_receiver_id(self):
        """A consumer that predates the deploy reads this field and nothing else."""
        event = Event(
            event_type=EventType.NOTIFICATION,
            sender_id=SENDER,
            target_type=TargetType.USER,
            target_id=USER,
            text="",
        )
        entry = EventCodec.to_redis(event)
        self.assertEqual(entry["receiver_id"], USER)
        self.assertEqual(entry["target_type"], "user")

    def test_a_stated_target_wins_over_a_disagreeing_receiver_id(self):
        event = Event(
            event_type=EventType.MESSAGE,
            sender_id=SENDER,
            receiver_id=str(uuid4()),
            target_type=TargetType.CHANNEL,
            target_id=CHANNEL,
            text="hi",
        )
        self.assertEqual(event.channel_id, CHANNEL)

    def test_a_stated_type_wins_over_the_inferred_one(self):
        """The point of the field: addressing no longer follows from the type."""
        event = Event(
            event_type=EventType.MESSAGE,
            sender_id=SENDER,
            target_type=TargetType.USER,
            target_id=USER,
            text="",
        )
        self.assertEqual(event.target_type, TargetType.USER)


class Accessors(unittest.TestCase):
    def test_reading_a_user_event_as_a_channel_raises(self):
        event = Event(
            event_type=EventType.NOTIFICATION, sender_id=SENDER, receiver_id=USER, text=""
        )
        with self.assertRaises(ValueError):
            event.channel_id

    def test_reading_a_channel_event_as_a_user_raises(self):
        event = Event(
            event_type=EventType.MESSAGE, sender_id=SENDER, receiver_id=CHANNEL, text=""
        )
        with self.assertRaises(ValueError):
            event.user_id

    def test_an_event_with_no_address_at_all_is_refused(self):
        with self.assertRaises(ValueError):
            Event(event_type=EventType.MESSAGE, sender_id=SENDER, text="hi")


class StreamEntriesFromBeforeTheDeploy(unittest.TestCase):
    """What the consumer reads off a shard that was written to by old code."""

    def test_to_grpc_fills_in_user_addressing(self):
        """An empty target_type here would read as channel and deliver nothing."""
        proto = EventCodec.to_grpc(legacy_stream_entry(EventType.NOTIFICATION, USER))
        self.assertEqual(proto.target_type, "user")
        self.assertEqual(proto.target_id, USER)
        self.assertEqual(proto.receiver_id, USER)

    def test_to_grpc_fills_in_channel_addressing(self):
        proto = EventCodec.to_grpc(legacy_stream_entry(EventType.MESSAGE, CHANNEL))
        self.assertEqual(proto.target_type, "channel")
        self.assertEqual(proto.target_id, CHANNEL)

    def test_to_pydantic_from_a_legacy_entry(self):
        event = EventCodec.to_pydantic(legacy_stream_entry(EventType.FRIEND_REQUEST, USER))
        self.assertEqual(event.target_type, TargetType.USER)
        self.assertEqual(event.user_id, USER)

    def test_a_proto_from_an_old_gateway_has_empty_target_fields(self):
        """proto3 sends "" for an unset string, which must count as missing."""
        proto = event_pb2.Event(
            event_id=str(uuid4()),
            event_type=EventType.NOTIFICATION.value,
            sender_id=SENDER,
            receiver_id=USER,
            text="",
            metadata="{}",
            timestamp="2026-08-23T12:00:00+00:00",
        )
        event = EventCodec.to_pydantic(proto)
        self.assertEqual(event.target_type, TargetType.USER)
        self.assertEqual(event.target_id, USER)


class RoundTrip(unittest.TestCase):
    """Producer -> stream -> consumer -> gRPC -> gateway, with nothing lost."""

    def test_addressing_survives_every_hop(self):
        cases = [
            (EventType.MESSAGE, TargetType.CHANNEL, CHANNEL),
            (EventType.VOICE_STATE, TargetType.CHANNEL, CHANNEL),
            (EventType.NOTIFICATION, TargetType.USER, USER),
            # Stated against what its type would imply, so inference cannot
            # be what makes it come out right
            (EventType.MESSAGE_UPDATE, TargetType.USER, USER),
        ]
        for event_type, target_type, target_id in cases:
            with self.subTest(event_type=event_type, target_type=target_type):
                original = Event(
                    event_type=event_type,
                    sender_id=SENDER,
                    target_type=target_type,
                    target_id=target_id,
                    text="x",
                    metadata={"action": "anything"},
                )
                entry = EventCodec.to_redis(original)
                proto = EventCodec.to_grpc(entry)
                received = EventCodec.to_pydantic(proto)

                self.assertEqual(received.event_id, original.event_id)
                self.assertEqual(received.target_type, target_type)
                self.assertEqual(received.target_id, target_id)
                self.assertEqual(received.receiver_id, target_id)
                self.assertEqual(received.metadata, original.metadata)


if __name__ == "__main__":
    unittest.main()
