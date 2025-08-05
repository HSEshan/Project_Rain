from fastapi import APIRouter
from src.auth.routes import router as auth_router
from src.guild.routes import router as guild_router

master_router = APIRouter(prefix="/api")

master_router.include_router(auth_router)
master_router.include_router(guild_router)

# TODO: Add other routes here
