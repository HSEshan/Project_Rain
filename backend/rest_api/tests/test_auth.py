from uuid import UUID, uuid4

from fastapi import Response, status
from fastapi.testclient import TestClient
from src.auth.schemas import UserCreate, UserResponse
from src.auth.service import AuthService
from src.utils.exceptions import AlreadyExistsException
from tests.conftest import override_dependency


class MockAuthService:
    def register_user(self, user: UserCreate) -> UserResponse:
        return UserResponse(id=uuid4(), email="test@test.com", username="test_user")


# Patch user service to return mock user
def test_register_user(test_client: TestClient) -> None:
    override_dependency(AuthService.register_user, MockAuthService.register_user)
    response: Response = test_client.post(
        "api/auth/register",
        json={
            "email": "test@test.com",
            "username": "test_user",
            "password": "Test@12345",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    assert isinstance(response_data["id"], UUID)
    assert response_data["email"] == "test@test.com"
    assert response_data["username"] == "test_user"


def test_user_already_exists(test_client: TestClient) -> None:
    override_dependency(
        AuthService.register_user,
        lambda user: AlreadyExistsException("User already exists"),
    )
    response: Response = test_client.post(
        "api/auth/register",
        json={
            "email": "test@test.com",
            "username": "test_user",
            "password": "Test@12345",
        },
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "User already exists"}
