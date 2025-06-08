import json
from unittest.mock import patch

from app.service.users import UserService
from app.utils.exceptions import AlreadyExistsException
from fastapi import Response, status
from fastapi.testclient import TestClient


# Patch user service to return mock user
def test_create_user(test_client: TestClient) -> None:
    with patch("app.service.users.UserService.create_user") as mock_create_user:
        mock_create_user.return_value = True
        response: Response = test_client.post(
            "/users",
            json={"email": "test@test.com", "username": "test", "password": "test"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {"message": "User test created successfully"}


def test_user_already_exists(test_client: TestClient) -> None:
    with patch("app.service.users.UserService.create_user") as mock_create_user:
        mock_create_user.side_effect = AlreadyExistsException("User already exists")
        response: Response = test_client.post(
            "/users",
            json={"email": "test@test.com", "username": "test", "password": "test"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {"detail": "User already exists"}
