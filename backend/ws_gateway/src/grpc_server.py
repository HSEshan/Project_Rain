import structlog
from grpc import aio
from src.websocket_manager import websocket_manager

from libs.event import event_pb2, event_pb2_grpc
from libs.event.codec import EventCodec

logger = structlog.get_logger()


class EventService(event_pb2_grpc.EventServiceServicer):
    async def SendEvent(self, request, context):
        logger.info(f"Processing event: {request}")

        event = EventCodec.to_pydantic(request)

        await websocket_manager.send_event(event)
        return event_pb2.Ack(success=True, message="Delivered")


async def serve_async_grpc_server(port: int):
    server = aio.server()
    event_pb2_grpc.add_EventServiceServicer_to_server(EventService(), server)
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    logger.info(f"Async gRPC server running on port {port}")
    await server.wait_for_termination()
