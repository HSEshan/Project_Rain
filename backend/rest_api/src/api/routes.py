from fastapi import APIRouter
from src.auth.routes import router as auth_router
from src.channel.routes import router as channel_router
from src.friendship.routes import router as friendship_router
from src.guild.routes import router as guild_router
from src.message.routes import router as message_router

master_router = APIRouter()

master_router.include_router(auth_router)
master_router.include_router(guild_router)
master_router.include_router(friendship_router)
master_router.include_router(channel_router)
master_router.include_router(message_router)
# TODO: Add other routes here
