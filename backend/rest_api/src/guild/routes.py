from fastapi import APIRouter, Depends, status
from src.auth.utils import user_dependency
from src.guild.schemas import GuildCreate, GuildMemberInvite
from src.guild.service import GuildService, get_guild_service

router = APIRouter(prefix="/guilds", tags=["guilds"])


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_user_guilds(
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.get_user_guilds(user)


@router.get("/{guild_id}", status_code=status.HTTP_200_OK)
async def get_guild_by_id(
    guild_id: str,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.get_guild_by_id(guild_id)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_guild(
    guild: GuildCreate,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.create_guild(user, guild)


@router.post("/{guild_id}/invite", status_code=status.HTTP_201_CREATED)
async def create_guild_invite(
    invite: GuildMemberInvite,
    current_user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.create_guild_invite(
        current_user, user_to_invite=invite.user_id, guild_id=invite.guild_id
    )


@router.post(
    "/{guild_id}/invites/{invite_id}/accept", status_code=status.HTTP_201_CREATED
)
async def accept_guild_invite(
    invite_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.accept_guild_invite(user, invite_id)


@router.delete(
    "/{guild_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_guild_member(
    guild_id: str,
    member_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.remove_guild_member(
        user=user, member_id=member_id, guild_id=guild_id
    )
