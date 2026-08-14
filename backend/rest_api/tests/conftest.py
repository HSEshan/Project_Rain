from typing import Any, Callable, Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from main import app as main_app


@pytest.fixture()
def test_client() -> Generator[TestClient, Any, None]:
    # Not used as a context manager on purpose: entering it runs the lifespan,
    # which connects to Postgres and runs migrations. These are unit tests and
    # must pass without a stack running — see backend/tests/e2e for the rest.
    client = TestClient(main_app)
    try:
        yield client
    finally:
        main_app.dependency_overrides.clear()


def override_dependency(
    dependency: Callable, mock_dependency: Callable, app: FastAPI = main_app
) -> None:
    app.dependency_overrides[dependency] = mock_dependency
