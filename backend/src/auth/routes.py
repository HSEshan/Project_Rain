from fastapi import APIRouter, Depends, status
from src.auth.schemas import Token, UserCreate, UserLogin
from src.auth.service import AuthService, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, service: AuthService = auth_service):
    return await service.register_user(user)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login_user(user: UserLogin, service: AuthService = auth_service):
    return await service.login_user(user)
