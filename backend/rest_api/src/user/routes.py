from fastapi import APIRouter, Depends, UploadFile
from src.auth.utils import user_dependency
from src.core.rate_limit import (
    PROFILE_USER,
    UPLOAD_IP,
    UPLOAD_USER,
    limit_ip,
    limit_user,
)
from src.user.schemas import (
    BulkUserRequest,
    BulkUserResponse,
    UserProfile,
    UserResponse,
    UserUpdate,
)
from src.user.service import UserService, get_user_service

router = APIRouter(prefix="/users", tags=["users"])


# `response_model` is load-bearing here, not decoration: the service returns the
# ORM `User`, which carries `email` and `password_hash`. See UserResponse.
@router.get("/", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    current_user: user_dependency,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.get_user_by_id(user_id)


@router.post("/bulk", response_model=BulkUserResponse)
async def get_users_by_ids(
    request: BulkUserRequest,
    current_user: user_dependency,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.get_users_by_ids(request)


# Declared before `/{user_id}/profile` so the literal wins the match. FastAPI
# resolves in declaration order and `me` is a valid uuid-shaped path segment as
# far as the router is concerned; the two do not collide today because the
# methods differ, and they will the moment either grows a sibling.
@router.patch(
    "/me",
    response_model=UserProfile,
    dependencies=[Depends(limit_user(PROFILE_USER))],
)
async def update_me(
    update: UserUpdate,
    current_user: user_dependency,
    user_service: UserService = Depends(get_user_service),
):
    """Edit your own profile.

    `me` rather than an id in the path: the only account anyone may edit is the
    one their token names, and a route that cannot express any other target
    cannot fail to check which one it was given.
    """
    return await user_service.update_me(current_user.id, update)


@router.put(
    "/me/avatar",
    response_model=UserProfile,
    dependencies=[Depends(limit_ip(UPLOAD_IP)), Depends(limit_user(UPLOAD_USER))],
)
async def set_my_avatar(
    file: UploadFile,
    current_user: user_dependency,
    user_service: UserService = Depends(get_user_service),
):
    """Upload a new avatar. PNG, JPEG, WebP or GIF; cropped square and re-encoded."""
    return await user_service.set_avatar(current_user.id, file)


@router.delete("/me/avatar", response_model=UserProfile)
async def clear_my_avatar(
    current_user: user_dependency,
    user_service: UserService = Depends(get_user_service),
):
    """Go back to the letter avatar."""
    return await user_service.clear_avatar(current_user.id)


@router.get("/{user_id}/profile", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    current_user: user_dependency,
    user_service: UserService = Depends(get_user_service),
):
    """Everything the profile card shows, scoped to whoever is asking."""
    return await user_service.get_profile(current_user.id, user_id)
