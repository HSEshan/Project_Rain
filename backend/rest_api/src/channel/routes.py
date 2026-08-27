from fastapi import APIRouter, Depends, status
from src.auth.utils import user_dependency
from src.channel.schemas import (
    ChannelMembers,
    ChannelResponse,
    DMChannelCreate,
    GroupDMCreate,
    GroupDMMemberAdd,
    GroupDMUpdate,
    GuildChannelCreate,
)
from src.channel.service import ChannelService, get_channel_service

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/me", response_model=list[ChannelResponse], status_code=status.HTTP_200_OK)
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


@router.post(
    "/dm", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED
)
async def create_dm_channel(
    channel_create: DMChannelCreate,
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    return await channel_service.create_dm_channel(user, channel_create)


@router.post(
    "/group", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED
)
async def create_group_dm(
    group_create: GroupDMCreate,
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    """A DM with more than two people. Everyone named must already be a friend."""
    return await channel_service.create_group_dm(user, group_create)


@router.post(
    "/guild/{guild_id}",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_guild_channel(
    guild_id: str,
    channel_create: GuildChannelCreate,
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    return await channel_service.create_guild_channel(user, guild_id, channel_create)


@router.get(
    "/{channel_id}", response_model=ChannelResponse, status_code=status.HTTP_200_OK
)
async def get_channel_by_id(
    user: user_dependency,
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service),
):
    return await channel_service.get_channel_by_id(user, channel_id)


@router.get(
    "/{channel_id}/members",
    response_model=ChannelMembers,
    status_code=status.HTTP_200_OK,
)
async def get_channel_members(
    channel_id: str,
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    """The full roster, caller included. `/bulk/participants` excludes them."""
    return await channel_service.get_channel_members(user, channel_id)


@router.patch(
    "/{channel_id}", response_model=ChannelResponse, status_code=status.HTTP_200_OK
)
async def update_group_dm(
    channel_id: str,
    update: GroupDMUpdate,
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    """Rename a group DM. Any member may; there is no hierarchy in one."""
    return await channel_service.update_group_dm(user, channel_id, update)


@router.post(
    "/{channel_id}/members",
    response_model=ChannelMembers,
    status_code=status.HTTP_201_CREATED,
)
async def add_group_dm_member(
    channel_id: str,
    member_add: GroupDMMemberAdd,
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    return await channel_service.add_group_dm_member(user, channel_id, member_add)


@router.delete("/{channel_id}/members/me", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group_dm(
    channel_id: str,
    user: user_dependency,
    channel_service: ChannelService = Depends(get_channel_service),
):
    """Leave a group. The last one out takes the channel with them."""
    await channel_service.leave_group_dm(user, channel_id)
