from unittest.mock import patch

from fastapi import Response, status
from fastapi.testclient import TestClient
from src.auth.schemas import UserResponse
from src.auth.service import AuthService
from src.utils.exceptions import AlreadyExistsException


# Patch user service to return mock user
def test_register_user(test_client: TestClient) -> None:
    with patch("src.auth.service.AuthService.register_user") as mock_register_user:
        mock_register_user.return_value = UserResponse(
            id=1, email="test@test.com", username="test_user"
        )
        response: Response = test_client.post(
            "api/auth/register",
            json={
                "email": "test@test.com",
                "username": "test_user",
                "password": "Test@12345",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "id": 1,
            "email": "test@test.com",
            "username": "test_user",
        }


def test_user_already_exists(test_client: TestClient) -> None:
    with patch("src.auth.service.AuthService.register_user") as mock_register_user:
        mock_register_user.side_effect = AlreadyExistsException("User already exists")
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
