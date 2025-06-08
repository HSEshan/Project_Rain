from app.schemas.users import UserCreate, UserDelete
from app.service.users import UserService, user_service_dependency
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=dict, status_code=201)
async def create_user(user: UserCreate, user_service: user_service_dependency):
    await user_service.create_user(user)
    return {"message": f"User {user.username} created successfully"}


@router.delete("/", response_model=dict, status_code=200)
async def delete_user(current_user, user_service: user_service_dependency):
    await user_service.delete_user(current_user)
    return {"message": f"User {current_user.username} deleted successfully"}
