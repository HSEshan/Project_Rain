from typing import Any, Callable, Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from main import app as main_app


@pytest.fixture(scope="session")
def test_client() -> Generator[TestClient, Any, None]:
    with TestClient(main_app) as _client:
        yield _client
    main_app.dependency_overrides = {}


def override_dependency(
    dependency: Callable, mock_dependency: Callable, app: FastAPI = main_app
) -> None:
    app.dependency_overrides[dependency] = mock_dependency
