from fastapi import APIRouter, Depends, UploadFile, status
from src.auth.utils import user_dependency
from src.core.rate_limit import (
    INVITE_ACCEPT_USER,
    INVITE_LINK_USER,
    INVITE_PREVIEW_IP,
    UPLOAD_IP,
    UPLOAD_USER,
    limit_ip,
    limit_user,
)
from src.guild.invite_links import InviteLinkService, get_invite_link_service
from src.guild.schemas import (
    GuildBanResponse,
    GuildCreate,
    GuildInviteResponse,
    GuildInviteSummary,
    GuildMemberInvite,
    GuildMemberResponse,
    GuildMemberRoleUpdate,
    GuildResponse,
    GuildTransfer,
    GuildUpdate,
    InviteLinkAccepted,
    InviteLinkCreate,
    InviteLinkPreview,
    InviteLinkResponse,
)
from src.guild.service import GuildService, get_guild_service

router = APIRouter(prefix="/guilds", tags=["guilds"])
# Its own prefix: holding a code is the whole point, so the guild is not in the path
invite_router = APIRouter(prefix="/invites", tags=["guilds"])


@router.get("/me", response_model=list[GuildResponse], status_code=status.HTTP_200_OK)
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


@router.get("/{guild_id}", response_model=GuildResponse, status_code=status.HTTP_200_OK)
async def get_guild_by_id(
    guild_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.get_guild_for_user(user, guild_id)


@router.patch("/{guild_id}", response_model=GuildResponse)
async def update_guild(
    guild_id: str,
    update: GuildUpdate,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    """Rename or redescribe a guild. Admins and the owner."""
    return await guild_service.update_guild(user, guild_id, update)


@router.delete("/{guild_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guild(
    guild_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    """Delete a guild, its channels and their messages. The owner only."""
    await guild_service.delete_guild(user, guild_id)


@router.get(
    "/{guild_id}/members",
    response_model=list[GuildMemberResponse],
    status_code=status.HTTP_200_OK,
)
async def get_guild_members(
    guild_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    await guild_service.check_guild_member(user.id, guild_id)
    return await guild_service.get_guild_members(guild_id)


@router.post("/", response_model=GuildResponse, status_code=status.HTTP_201_CREATED)
async def create_guild(
    guild: GuildCreate,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.create_guild(user, guild)


@router.post(
    "/{guild_id}/invite",
    response_model=GuildInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
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
    "/{guild_id}/invites/{invite_id}/accept",
    response_model=GuildMemberResponse,
    status_code=status.HTTP_201_CREATED,
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


@router.post("/{guild_id}/transfer", response_model=GuildResponse)
async def transfer_guild(
    guild_id: str,
    transfer: GuildTransfer,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    """Give the guild to another member. The owner only; they stay an admin."""
    return await guild_service.transfer_ownership(user, guild_id, transfer.user_id)


# Declared before `/{member_id}` so the literal path wins the match
@router.delete("/{guild_id}/members/me", status_code=status.HTTP_204_NO_CONTENT)
async def leave_guild(
    guild_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    """Leave. The owner has to transfer the guild or delete it instead."""
    await guild_service.leave_guild(user, guild_id)


@router.patch("/{guild_id}/members/{member_id}", response_model=GuildMemberResponse)
async def update_guild_member_role(
    guild_id: str,
    member_id: str,
    update: GuildMemberRoleUpdate,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    """Change someone's role. Only for someone you outrank."""
    return await guild_service.update_member_role(
        user, guild_id, member_id, update.role
    )


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


@router.post("/{guild_id}/bans/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def ban_guild_member(
    guild_id: str,
    member_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    """Remove someone you outrank, and keep them out."""
    await guild_service.remove_guild_member(
        user=user, member_id=member_id, guild_id=guild_id, ban=True
    )


@router.get("/{guild_id}/bans", response_model=list[GuildBanResponse])
async def list_guild_bans(
    guild_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    return await guild_service.list_bans(user, guild_id)


@router.delete("/{guild_id}/bans/{banned_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_guild_ban(
    guild_id: str,
    banned_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    await guild_service.remove_ban(user, guild_id, banned_id)


@router.post(
    "/{guild_id}/invite-links",
    response_model=InviteLinkResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_user(INVITE_LINK_USER))],
)
async def create_invite_link(
    guild_id: str,
    create: InviteLinkCreate,
    user: user_dependency,
    links: InviteLinkService = Depends(get_invite_link_service),
):
    return await links.create_link(user, guild_id, create)


@router.get("/{guild_id}/invite-links", response_model=list[InviteLinkResponse])
async def list_invite_links(
    guild_id: str,
    user: user_dependency,
    links: InviteLinkService = Depends(get_invite_link_service),
):
    """Live links. Admins see all of them, anyone else the ones they made."""
    return await links.list_links(user, guild_id)


@router.delete(
    "/{guild_id}/invite-links/{code}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_invite_link(
    guild_id: str,
    code: str,
    user: user_dependency,
    links: InviteLinkService = Depends(get_invite_link_service),
):
    await links.revoke_link(user, guild_id, code)


@invite_router.get(
    "/{code}",
    response_model=InviteLinkPreview,
    dependencies=[Depends(limit_ip(INVITE_PREVIEW_IP))],
)
async def preview_invite_link(
    code: str,
    links: InviteLinkService = Depends(get_invite_link_service),
):
    """Public: this is what someone sees before they have an account."""
    return await links.preview(code)


@invite_router.post(
    "/{code}/accept",
    response_model=InviteLinkAccepted,
    dependencies=[Depends(limit_user(INVITE_ACCEPT_USER))],
)
async def accept_invite_link(
    code: str,
    user: user_dependency,
    links: InviteLinkService = Depends(get_invite_link_service),
):
    return await links.accept(user, code)


@router.put(
    "/{guild_id}/icon",
    response_model=GuildResponse,
    dependencies=[Depends(limit_ip(UPLOAD_IP)), Depends(limit_user(UPLOAD_USER))],
)
async def set_guild_icon(
    guild_id: str,
    file: UploadFile,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    """Replace the guild's icon. Admins only."""
    return await guild_service.set_icon(user, guild_id, file)


@router.delete("/{guild_id}/icon", response_model=GuildResponse)
async def clear_guild_icon(
    guild_id: str,
    user: user_dependency,
    guild_service: GuildService = Depends(get_guild_service),
):
    """Back to the letter icon. Admins only."""
    return await guild_service.clear_icon(user, guild_id)
