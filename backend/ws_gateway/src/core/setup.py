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

# A gateway proves it is alive by keeping this key fresh. Short enough that a
# crashed gateway's routes are pruned on the first failed delivery after about
# fifteen seconds; the refresh is a third of it, so one slow Redis round trip
# does not make a live gateway look dead.
HEARTBEAT_TTL_SECONDS = 15
HEARTBEAT_INTERVAL_SECONDS = 5
# Every this many heartbeats (30s), write this gateway's routes again. A route the
# consumer pruned by mistake, or that a Redis restart lost, comes back within it.
REASSERT_EVERY = 6


async def heartbeat_loop(redis_manager: RedisManager, endpoint: str) -> None:
    """Refresh this gateway's heartbeat until cancelled. Never raises.

    Every REASSERT_EVERY beats it also re-writes this gateway's routes; see
    `WebsocketManager.reassert_routes`. A detached task, which AGENTS.md warns about, and the reason it catches and
    logs every failure itself: there is nobody awaiting it to hear one. A Redis
    outage costs the heartbeat, which only matters if a delivery to this gateway
    also fails, and the next refresh after the outage restores it.
    """
    beats = 0
    while True:
        try:
            await redis_manager.set_gateway_heartbeat(endpoint, HEARTBEAT_TTL_SECONDS)
            beats += 1
            if beats % REASSERT_EVERY == 0:
                await websocket_manager.reassert_routes()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Gateway heartbeat failed", endpoint=endpoint)
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_manager = RedisManager()
    await redis_manager.connect(
        settings.REDIS_HOST, settings.REDIS_PORT, settings.REDIS_DB
    )
    websocket_manager.set_redis_manager(redis_manager)
    server_task = asyncio.create_task(serve_grpc_server(settings.GRPC_PORT))
    # Say out loud what this instance thinks other services should reach it on.
    # It is the first thing to check when a replica's events go missing.
    logger.info(
        "Advertising gRPC endpoint",
        endpoint=settings.GRPC_ENDPOINT,
        explicit=bool(settings.GRPC_ADVERTISE_HOST),
    )
    websocket_manager.set_grpc_endpoint(settings.GRPC_ENDPOINT)
    # Written once before accepting anything, so no socket is ever routed to an
    # endpoint the consumer could mistake for a dead one.
    await redis_manager.set_gateway_heartbeat(
        settings.GRPC_ENDPOINT, HEARTBEAT_TTL_SECONDS
    )
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(redis_manager, settings.GRPC_ENDPOINT)
    )
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

    heartbeat_task.cancel()
    try:
        # Sockets have closed by now, and each close removed its user's routes.
        # Dropping the heartbeat as well means that if anything was left
        # behind, the first failed delivery to it prunes it at once rather than
        # after the TTL.
        await redis_manager.delete_gateway_heartbeat(settings.GRPC_ENDPOINT)
    except Exception:
        logger.exception("Could not remove the gateway heartbeat on shutdown")
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
