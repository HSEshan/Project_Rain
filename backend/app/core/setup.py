from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

# from app.api.v1 import router as api_router
from app.core.config import settings
from app.core.utils import shutdown_event, startup_event
from fastapi import APIRouter, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, None]:
    try:
        await startup_event()
        yield
    finally:
        await shutdown_event()


health_router = APIRouter(tags=["Health Check"])


@health_router.get("/", status_code=status.HTTP_200_OK)
def read_root():
    return {"status": "OK"}


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, log_level="debug")
    app.include_router(health_router)
    # app.include_router(api_router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if not settings.DOCS:
        app.docs_url = None
        app.redoc_url = None
        app.openapi_url = None
    return app
