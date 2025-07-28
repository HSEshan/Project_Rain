from fastapi import Response, status
from fastapi.testclient import TestClient


def test_root(test_client: TestClient) -> None:

    response: Response = test_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "OK"}


def test_non_existent_route(test_client: TestClient) -> None:

    response: Response = test_client.get("/non_existent_route")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Not Found"}
