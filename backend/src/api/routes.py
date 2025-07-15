from fastapi import APIRouter
from src.auth.routes import router as auth_router

master_router = APIRouter(prefix="/api")

master_router.include_router(auth_router)
