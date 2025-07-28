from functools import singledispatch
import json

from .schema import Event
from . import event_pb2


class EventCodec:
    """
    EventCodec is a class that provides methods to convert events between different formats.
    Currently supported formats are:
    - Event (Pydantic)
    - dict (Redis)
    - Protobuf
    """

    @staticmethod
    @singledispatch
    def to_grpc(event) -> event_pb2.Event:
        raise ValueError(f"Unsupported event type: {type(event)}")

    # Handler for Event (Pydantic)
    @to_grpc.register
    @staticmethod
    def _(event: Event) -> event_pb2.Event:
        return event_pb2.Event(
            event_id=str(event.event_id),
            event_type=event.event_type.value,
            sender_id=str(event.sender_id),
            receiver_id=str(event.receiver_id),
            text=event.text,
            metadata=json.dumps(event.metadata or {}),
            timestamp=event.timestamp,
        )

    # Handler for dict (Redis)
    @to_grpc.register
    @staticmethod
    def _(event: dict) -> event_pb2.Event:
        return event_pb2.Event(
            event_id=event["event_id"],
            event_type=event["event_type"],
            sender_id=event["sender_id"],
            receiver_id=event["receiver_id"],
            text=event["text"],
            metadata=json.dumps(event.get("metadata") or {}),
            timestamp=event["timestamp"],
        )
        
    @staticmethod
    def to_pydantic(event) -> Event:
        raise ValueError(f"Unsupported event type: {type(event)}")
    
    # Handler for Protobuf
    @to_pydantic.register
    @staticmethod
    def _(event: event_pb2.Event) -> Event:
        return Event(
            event_id=event.event_id,
            event_type=event.event_type,
            sender_id=event.sender_id,
            receiver_id=event.receiver_id,
            text=event.text,
            metadata=json.loads(event.metadata or '{}'),
            timestamp=event.timestamp,
        )
    
    # Handler for Redis
    @to_pydantic.register
    @staticmethod
    def _(event: dict[str, str]) -> Event:
        return Event(
            event_id=event["event_id"],
            event_type=event["event_type"],
            sender_id=event["sender_id"],
            receiver_id=event["receiver_id"],
            text=event["text"],
            metadata=json.loads(event.get("metadata") or '{}'),
            timestamp=event["timestamp"],
        )
    
    @staticmethod
    def to_redis(event) -> dict[str, str]:
        raise ValueError(f"Unsupported event type: {type(event)}")
    
    # Handler for Event
    @to_redis.register
    @staticmethod
    def _(event: Event) -> dict[str, str]:
        return {
            "event_id": str(event.event_id),
            "event_type": event.event_type.value,
            "sender_id": str(event.sender_id),
            "receiver_id": str(event.receiver_id),
            "text": event.text,
            "metadata": json.dumps(event.metadata or {}),
            "timestamp": event.timestamp,
        }
    
    # Handler for Protobuf
    @to_redis.register
    @staticmethod
    def _(event: event_pb2.Event) -> dict[str, str]:
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "sender_id": event.sender_id,
            "receiver_id": event.receiver_id,
            "text": event.text,
            "metadata": json.dumps(event.metadata or {}),
            "timestamp": event.timestamp,
        }