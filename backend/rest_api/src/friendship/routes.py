from fastapi import APIRouter, Depends, status
from src.auth.utils import user_dependency
from src.friendship.schemas import FriendRequestCreate
from src.friendship.service import FriendshipService, get_friendship_service

router = APIRouter(prefix="/friendship", tags=["friendship"])


@router.get("/friends/me", status_code=status.HTTP_200_OK)
async def get_user_friends(
    user: user_dependency,
    friendship_service: FriendshipService = Depends(get_friendship_service),
):
    return await friendship_service.get_user_friends(user.id)


@router.get("/friends/request/me", status_code=status.HTTP_200_OK)
async def get_user_friend_requests(
    user: user_dependency,
    friendship_service: FriendshipService = Depends(get_friendship_service),
):
    return await friendship_service.get_friend_requests_by_user_id(user.id)


@router.post("/friends/request", status_code=status.HTTP_201_CREATED)
async def create_friend_request(
    current_user: user_dependency,
    to_username: str,
    friendship_service: FriendshipService = Depends(get_friendship_service),
):
    return await friendship_service.create_friend_request(
        FriendRequestCreate(from_user_id=current_user.id, to_username=to_username)
    )


@router.post(
    "/friends/request/{friend_request_id}/accept", status_code=status.HTTP_200_OK
)
async def accept_friend_request(
    friend_request_id: str,
    current_user: user_dependency,
    friendship_service: FriendshipService = Depends(get_friendship_service),
):
    return await friendship_service.accept_friend_request(
        current_user.id, friend_request_id
    )


@router.post(
    "/friends/request/{friend_request_id}/reject", status_code=status.HTTP_200_OK
)
async def reject_friend_request(
    friend_request_id: str,
    current_user: user_dependency,
    friendship_service: FriendshipService = Depends(get_friendship_service),
):
    return await friendship_service.reject_friend_request(
        current_user.id, friend_request_id
    )
