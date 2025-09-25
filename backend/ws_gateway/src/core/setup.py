import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import APIRouter, FastAPI
from sqlalchemy import text
from src.api.router import router as websocket_router
from src.core.config import settings
from src.database.config import engine
from src.event.event_dispatcher import event_dispatcher
from src.event.event_queue import event_queue
from src.grpc.grpc_server import serve_grpc_server
from src.redis.redis_manager import RedisManager
from src.websocket.manager import websocket_manager

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_manager = RedisManager()
    await redis_manager.connect(
        settings.REDIS_HOST, settings.REDIS_PORT, settings.REDIS_DB
    )
    websocket_manager.set_redis_manager(redis_manager)
    server_task = asyncio.create_task(serve_grpc_server(settings.GRPC_PORT))
    websocket_manager.set_grpc_endpoint(settings.GRPC_ENDPOINT)
    event_queue.set_event_dispatcher(event_dispatcher)
    event_dispatcher.set_redis_manager(redis_manager)
    event_dispatcher.set_websocket_manager(websocket_manager)
    await event_queue.start_batch_processor()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise e

    yield

    server_task.cancel()
    await redis_manager.disconnect()


health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health_check():
    return {"status": "ok"}


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(websocket_router)
    return app
