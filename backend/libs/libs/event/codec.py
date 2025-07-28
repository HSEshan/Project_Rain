import json

from . import event_pb2
from .schema import Event


class EventCodec:
    """
    EventCodec is a class that provides methods to convert events between different formats.
    Currently supported formats are:
    - Event (Pydantic)
    - dict (Redis)
    - Protobuf
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
                metadata=json.dumps(event.metadata or {}),
                timestamp=event.timestamp,
            )
        elif isinstance(event, dict):
            return event_pb2.Event(
                event_id=event["event_id"],
                event_type=event["event_type"],
                sender_id=event["sender_id"],
                receiver_id=event["receiver_id"],
                text=event["text"],
                metadata=json.dumps(event.get("metadata") or {}),
                timestamp=event["timestamp"],
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
                metadata=json.loads(event.metadata or "{}"),
                timestamp=event.timestamp,
            )
        elif isinstance(event, dict):
            return Event(
                event_id=event["event_id"],
                event_type=event["event_type"],
                sender_id=event["sender_id"],
                receiver_id=event["receiver_id"],
                text=event["text"],
                metadata=json.loads(event.get("metadata") or "{}"),
                timestamp=event["timestamp"],
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
                "metadata": json.dumps(event.metadata or {}),
                "timestamp": event.timestamp,
            }
        elif isinstance(event, event_pb2.Event):
            return {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "sender_id": event.sender_id,
                "receiver_id": event.receiver_id,
                "text": event.text,
                "metadata": json.dumps(event.metadata or {}),
                "timestamp": event.timestamp,
            }
        else:
            raise ValueError(f"Unsupported event type: {type(event)}")
