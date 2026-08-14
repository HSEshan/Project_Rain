from fastapi import APIRouter, Depends, status
from src.auth.utils import user_dependency
from src.guild.schemas import GuildCreate, GuildInviteSummary, GuildMemberInvite
from src.guild.service import GuildService, get_guild_service

router = APIRouter(prefix="/guilds", tags=["guilds"])


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_user_guilds(
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.get_user_guilds(user)


# Declared before `/{guild_id}` so the literal path wins the match
@router.get(
    "/invites/me",
    response_model=list[GuildInviteSummary],
    status_code=status.HTTP_200_OK,
)
async def get_user_guild_invites(
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.get_user_guild_invites(user)


@router.get("/{guild_id}", status_code=status.HTTP_200_OK)
async def get_guild_by_id(
    guild_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.get_guild_for_user(user, guild_id)


@router.get("/{guild_id}/members", status_code=status.HTTP_200_OK)
async def get_guild_members(
    guild_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    await guild_service.check_guild_member(user.id, guild_id)
    return await guild_service.get_guild_members(guild_id)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_guild(
    guild: GuildCreate,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.create_guild(user, guild)


@router.post("/{guild_id}/invite", status_code=status.HTTP_201_CREATED)
async def create_guild_invite(
    guild_id: str,
    invite: GuildMemberInvite,
    current_user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.create_guild_invite(
        current_user,
        guild_id=guild_id,
        user_to_invite=invite.user_id,
        username=invite.username,
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
    "/{guild_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def decline_guild_invite(
    invite_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    await guild_service.decline_guild_invite(user, invite_id)


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
