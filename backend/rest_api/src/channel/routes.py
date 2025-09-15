from fastapi import APIRouter, Depends, status
from src.auth.utils import user_dependency
from src.channel.schemas import DMChannelCreate, GuildChannelCreate
from src.channel.service import ChannelService, get_channel_service

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_user_channels(
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    return await channel_service.get_user_channels(user)


@router.post("/bulk/participants", status_code=status.HTTP_200_OK)
async def get_channel_participants(
    channel_ids: list[str],
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    return await channel_service.get_channel_participants(user, channel_ids)


@router.post("/dm", status_code=status.HTTP_201_CREATED)
async def create_dm_channel(
    channel_create: DMChannelCreate,
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    return await channel_service.create_dm_channel(channel_create)


@router.post("/guild", status_code=status.HTTP_201_CREATED)
async def create_guild_channel(
    channel_create: GuildChannelCreate,
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    return await channel_service.create_guild_channel(user, channel_create)


@router.get("/{channel_id}", status_code=status.HTTP_200_OK)
async def get_channel_by_id(
    user: user_dependency,
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service),
):
    return await channel_service.get_channel_by_id(user, channel_id)
