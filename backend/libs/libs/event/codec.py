import json

from . import event_pb2
from .schema import Event, target_type_for


class EventCodec:
    """
    EventCodec is a class that provides methods to convert events between different formats.
    Currently supported formats are:
    - Event (Pydantic)
    - dict (Redis)
    - Protobuf

    Every direction carries both `receiver_id` and `target_type`/`target_id`
    during the addressing migration, and every read tolerates the new pair being
    absent, because entries written before the deploy are still in the streams.
    See devnotes.md, Appendix A1.
    """

    @staticmethod
    def to_grpc(event: Event | dict[str, str]) -> event_pb2.Event:
        if isinstance(event, Event):
            return event_pb2.Event(
                event_id=str(event.event_id),
                event_type=event.event_type.value,
                sender_id=str(event.sender_id),
                receiver_id=str(event.receiver_id),
                text=event.text,
                metadata=json.dumps(event.metadata or {}),  # Serialise from pydantic
                timestamp=event.timestamp,
                target_type=event.target_type.value,
                target_id=event.target_id,
            )
        elif isinstance(event, dict):
            return event_pb2.Event(
                event_id=event["event_id"],
                event_type=event["event_type"],
                sender_id=event["sender_id"],
                receiver_id=event["receiver_id"],
                text=event["text"],
                metadata=event["metadata"],  # Already serialized
                timestamp=event["timestamp"],
                # A stream entry written before the migration has neither
                # field. They have to be filled in *here* rather than left
                # empty: this is the path the consumer routes on, and an empty
                # target_type would read as "channel" and send a user-addressed
                # notification to a channel lookup that returns nothing.
                target_type=(
                    event.get("target_type")
                    or target_type_for(event["event_type"]).value
                ),
                target_id=event.get("target_id") or event["receiver_id"],
            )
        else:
            raise ValueError(f"Unsupported event type: {type(event)}")

    @staticmethod
    def to_pydantic(event: event_pb2.Event | dict[str, str]) -> Event:
        if isinstance(event, event_pb2.Event):
            return Event(
                event_id=event.event_id,
                event_type=event.event_type,
                sender_id=event.sender_id,
                receiver_id=event.receiver_id,
                text=event.text,
                metadata=json.loads(event.metadata or "{}"),  # Deserialise to dict
                timestamp=event.timestamp,
                # proto3 gives "" rather than absent for an unset string, and
                # Event treats empty the same as missing
                target_type=event.target_type or None,
                target_id=event.target_id,
            )
        elif isinstance(event, dict):
            return Event(
                event_id=event["event_id"],
                event_type=event["event_type"],
                sender_id=event["sender_id"],
                receiver_id=event["receiver_id"],
                text=event["text"],
                metadata=json.loads(
                    event.get("metadata") or "{}"
                ),  # Deserialise to dict
                timestamp=event["timestamp"],
                target_type=event.get("target_type") or None,
                target_id=event.get("target_id", ""),
            )
        else:
            raise ValueError(f"Unsupported event type: {type(event)}")

    @staticmethod
    def to_redis(event: Event | event_pb2.Event) -> dict[str, str]:
        if isinstance(event, Event):
            return {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "sender_id": event.sender_id,
                "receiver_id": event.receiver_id,
                "text": event.text,
                "metadata": json.dumps(event.metadata or {}),  # Serialise from pydantic
                "timestamp": event.timestamp,
                "target_type": event.target_type.value,
                "target_id": event.target_id,
            }
        elif isinstance(event, event_pb2.Event):
            return {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "sender_id": event.sender_id,
                "receiver_id": event.receiver_id,
                "text": event.text,
                "metadata": event.metadata,  # Already serialized
                "timestamp": event.timestamp,
                "target_type": event.target_type,
                "target_id": event.target_id,
            }
        else:
            raise ValueError(f"Unsupported event type: {type(event)}")
