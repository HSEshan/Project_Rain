import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from src.core.config import settings
from src.grpc_server import serve_async_grpc_server
from src.redis_manager import RedisManager
from src.websocket_manager import websocket_manager
from src.router import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_manager = RedisManager()
    await redis_manager.connect(
        settings.REDIS_HOST, settings.REDIS_PORT, settings.REDIS_DB
    )
    websocket_manager.set_redis_manager(redis_manager)
    server_task = asyncio.create_task(serve_async_grpc_server(settings.GRPC_PORT))
    websocket_manager.set_grpc_endpoint(settings.GRPC_ENDPOINT)

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
