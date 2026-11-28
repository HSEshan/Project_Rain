from fastapi.testclient import TestClient
from src.core.config import SettingsFactory

PROD = "https://voice.eshanhs.dev"


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/auth/refresh",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )


def test_default_allows_prod_origin_with_credentials(test_client: TestClient) -> None:
    response = _preflight(test_client, PROD)
    assert response.headers.get("access-control-allow-origin") == PROD
    assert response.headers.get("access-control-allow-credentials") == "true"

    simple = test_client.get("/health", headers={"Origin": PROD})
    assert simple.headers.get("access-control-allow-origin") == PROD


def test_sibling_subdomain_is_not_allowed(test_client: TestClient) -> None:
    evil = "https://evil.eshanhs.dev"
    response = _preflight(test_client, evil)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers

    simple = test_client.get("/health", headers={"Origin": evil})
    # Starlette sends Allow-Credentials on every response; without a matching
    # Allow-Origin the browser still refuses to expose the body.
    assert "access-control-allow-origin" not in simple.headers


def test_origin_list_parsing_drops_wildcard_and_blanks() -> None:
    settings = SettingsFactory.model_construct(
        CORS_ALLOWED_ORIGINS=" https://a.example/ , *, ,http://localhost:8080"
    )
    assert settings.cors_origins == ["https://a.example", "http://localhost:8080"]


def test_default_includes_prod_origin() -> None:
    default = SettingsFactory.model_fields["CORS_ALLOWED_ORIGINS"].default
    assert PROD in default.split(",")
