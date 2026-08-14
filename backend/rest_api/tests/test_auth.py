from uuid import UUID, uuid4

from fastapi import Response, status
from fastapi.testclient import TestClient
from src.auth.schemas import UserCreate, UserResponse
from src.auth.service import get_auth_service
from src.utils.exceptions import AlreadyExistsException
from tests.conftest import override_dependency

# The route depends on `get_auth_service`, not on `AuthService.register_user`,
# so that is what has to be overridden — the previous version patched an
# unbound method FastAPI never resolved, and every request hit the real
# database. `register_user` is also awaited, so the double must be async.


class StubAuthService:
    def __init__(self, raises: Exception | None = None):
        self._raises = raises

    async def register_user(self, user: UserCreate) -> UserResponse:
        if self._raises:
            raise self._raises
        return UserResponse(id=str(uuid4()), email=user.email, username=user.username)


def test_register_user(test_client: TestClient) -> None:
    override_dependency(get_auth_service, lambda: StubAuthService())

    response: Response = test_client.post(
        "/auth/register",
        json={
            "email": "test@test.com",
            "username": "test_user",
            "password": "Test@12345",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    UUID(body["id"])  # raises if the id is not a uuid
    assert body["email"] == "test@test.com"
    assert body["username"] == "test_user"


def test_user_already_exists(test_client: TestClient) -> None:
    override_dependency(
        get_auth_service,
        lambda: StubAuthService(AlreadyExistsException("User already exists")),
    )

    response: Response = test_client.post(
        "/auth/register",
        json={
            "email": "test@test.com",
            "username": "test_user",
            "password": "Test@12345",
        },
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "User already exists"}
