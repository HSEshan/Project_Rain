from fastapi import APIRouter, Depends, status
from src.auth.utils import user_dependency
from src.guild.schemas import GuildCreate
from src.guild.service import GuildService, get_guild_service

router = APIRouter(prefix="/guilds", tags=["guilds"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_guild(
    guild: GuildCreate,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.create_guild(user, guild)
