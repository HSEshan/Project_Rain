from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.api.routes import master_router
from src.core.config import settings
from src.core.utils import shutdown_event, startup_event


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, None]:
    try:
        await startup_event()
        yield
    finally:
        await shutdown_event()


health_router = APIRouter(tags=["Health Check"])


@health_router.get("/health", status_code=status.HTTP_200_OK)
def read_root():
    return {"status": "OK"}


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422s without the value that failed.

    FastAPI's default handler echoes the offending input back in each error, so
    a rejected registration returned the submitted **password in plaintext** in
    its own error body. It only ever goes to the person who typed it, but it
    also lands in whatever that browser logs, and a password has no business
    being in an error payload at all.

    `type`, `loc` and `msg` are kept, which is everything a client needs to say
    what went wrong and about which field.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": [
                {"type": error["type"], "loc": error["loc"], "msg": error["msg"]}
                for error in exc.errors()
            ]
        },
    )


def create_app() -> FastAPI:
    # The docs flag has to be passed to the constructor. FastAPI registers the
    # /docs, /redoc and /openapi.json routes during __init__, so assigning
    # app.docs_url = None afterwards left every one of them serving — DOCS=false
    # looked like it worked and disabled nothing.
    docs = settings.DOCS
    app = FastAPI(
        lifespan=lifespan,
        log_level="debug",
        title="Project Rain API",
        description="API for Project Rain",
        version="0.5.0",
        root_path="/api",
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(health_router)
    app.include_router(master_router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
