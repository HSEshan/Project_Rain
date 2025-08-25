import structlog
from grpc import aio
from libs.event import event_pb2, event_pb2_grpc
from libs.event.codec import EventCodec
from libs.logging import bind_event_context
from src.event_processor import event_processor

logger = structlog.get_logger()


@bind_event_context(event_arg_name="request")
class EventService(event_pb2_grpc.EventServiceServicer):
    async def SendEvent(self, request, context):
        event = EventCodec.to_pydantic(request)
        logger.debug(f"Received event: {event}")

        await event_processor.send_event_to_clients(event)
        logger.debug("Event sent to processor")
        return event_pb2.Ack(success=True, message="Delivered")


async def serve_async_grpc_server(port: int):
    try:
        server = aio.server()
        event_pb2_grpc.add_EventServiceServicer_to_server(EventService(), server)
        server.add_insecure_port(f"[::]:{port}")
        await server.start()
        logger.info(f"Async gRPC server running on port {port}")
        await server.wait_for_termination()
    except Exception as e:
        logger.critical(f"Error starting gRPC server: {e}")
        raise e
