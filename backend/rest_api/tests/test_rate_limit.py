"""Whose request this is, and what a refusal looks like. No Redis, no database.

`client_address` is the security property here: a limit keyed on something the
client controls is no limit at all.
"""

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from libs.rate_limit import RateLimit
from src.core import rate_limit
from src.core.rate_limit import client_address, limit_ip
from src.utils.exceptions import RateLimitedException


def request_with(headers: dict[str, str], peer: str = "172.18.0.5") -> Request:
    return Request(
        {
            "type": "http",
            "headers": [
                (key.lower().encode(), value.encode()) for key, value in headers.items()
            ],
            "client": (peer, 1234),
        }
    )


def test_reads_the_address_the_edge_set():
    assert client_address(request_with({"X-Real-IP": "203.0.113.7"})) == "203.0.113.7"


def test_x_forwarded_for_is_ignored():
    # The leftmost entry of this header is whatever the client chose to send
    request = request_with(
        {"X-Real-IP": "203.0.113.7", "X-Forwarded-For": "1.2.3.4, 203.0.113.7"}
    )
    assert client_address(request) == "203.0.113.7"


def test_x_forwarded_for_alone_is_not_trusted_either():
    request = request_with({"X-Forwarded-For": "1.2.3.4"}, peer="172.18.0.5")
    assert client_address(request) == "172.18.0.5"


def test_falls_back_to_the_socket_peer():
    assert client_address(request_with({}, peer="172.18.0.5")) == "172.18.0.5"


def test_ipv6_is_grouped_by_slash_64():
    first = client_address(request_with({"X-Real-IP": "2001:db8:1:2:aaaa::1"}))
    second = client_address(request_with({"X-Real-IP": "2001:db8:1:2:bbbb::2"}))
    other = client_address(request_with({"X-Real-IP": "2001:db8:1:3::1"}))
    assert first == second
    assert first != other


def test_a_header_that_is_not_an_address_is_still_an_identity():
    assert client_address(request_with({"X-Real-IP": "nonsense"})) == "nonsense"


@pytest.mark.parametrize(
    "seconds, text",
    [
        (1, "1 second"),
        (42, "42 seconds"),
        (60, "1 minute"),
        (61, "2 minutes"),
        (3600, "60 minutes"),
    ],
)
def test_the_refusal_is_a_sentence_with_a_number_in_it(seconds, text):
    exc = RateLimitedException(seconds)
    assert exc.status_code == 429
    assert exc.headers == {"Retry-After": str(seconds)}
    assert text in exc.detail


class FakeRedis:
    def __init__(self):
        self.count = 0

    async def eval(self, *args):
        self.count += 1
        return [self.count, 30]


def test_a_route_answers_429_with_retry_after(monkeypatch):
    monkeypatch.setattr(rate_limit.realtime_publisher, "redis", FakeRedis())
    monkeypatch.setattr(rate_limit.settings, "RATE_LIMIT_ENABLED", True)

    app = FastAPI()

    @app.get("/", dependencies=[Depends(limit_ip(RateLimit("t", 1, 60)))])
    def route():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/").status_code == 200
    refused = client.get("/")
    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "30"
    assert "30 seconds" in refused.json()["detail"]


def test_the_switch_turns_it_off(monkeypatch):
    monkeypatch.setattr(rate_limit.realtime_publisher, "redis", FakeRedis())
    monkeypatch.setattr(rate_limit.settings, "RATE_LIMIT_ENABLED", False)

    app = FastAPI()

    @app.get("/", dependencies=[Depends(limit_ip(RateLimit("t", 1, 60)))])
    def route():
        return {"ok": True}

    client = TestClient(app)
    assert [client.get("/").status_code for _ in range(3)] == [200, 200, 200]
