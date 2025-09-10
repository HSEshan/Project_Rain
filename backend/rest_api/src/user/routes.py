from fastapi import APIRouter, Depends
from src.user.schemas import BulkUserRequest
from src.user.service import UserService, get_user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/")
async def get_user_by_id(
    user_id: str,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.get_user_by_id(user_id)


@router.post("/bulk")
async def get_users_by_ids(
    request: BulkUserRequest,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.get_users_by_ids(request)
