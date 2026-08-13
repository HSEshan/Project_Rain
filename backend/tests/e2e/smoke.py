"""End-to-end smoke test for Project Rain.

Runs against a live `docker compose up` stack (Caddy on :8080). Stdlib only, so
it needs no host virtualenv:

    docker compose up -d
    python backend/tests/e2e/smoke.py

It covers the Phase 1 acceptance path — register, friend, DM, guild create,
guild channels, invite accept — plus the websocket round trip (message ->
postgres -> second client), which is driven inside the ws_gateway container.

It creates real rows in the dev database; user names are randomised per run.
"""

import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = "http://localhost:8080/api"
FAILURES: list[str] = []


def call(method, path, body=None, token=None, expect=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            status, payload = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        status, payload = e.code, e.read().decode()
    except urllib.error.URLError as e:
        raise SystemExit(f"Cannot reach {BASE} ({e}). Is `docker compose up` running?")

    try:
        parsed = json.loads(payload) if payload else None
    except json.JSONDecodeError:
        parsed = payload

    if expect is not None and status != expect:
        FAILURES.append(f"{method} {path} -> {status} (expected {expect}): {parsed}")
    return status, parsed


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(f"{name} {detail}")


def register(tag):
    """Register a user and return their id + bearer token."""
    username = f"{tag}_{uuid.uuid4().hex[:8]}"
    creds = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "Passw0rd!23",
    }
    status, created = call("POST", "/auth/register", creds, expect=201)
    if status != 201:
        raise SystemExit(f"register failed for {username}: {status} {created}")

    # /auth/login takes an OAuth2 password form, not JSON
    form = urllib.parse.urlencode(
        {"username": creds["email"], "password": creds["password"]}
    ).encode()
    req = urllib.request.Request(BASE + "/auth/login", data=form, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read().decode())["access_token"]

    return {"id": created["id"], "username": username, "token": token}


def run_websocket_probe(sender, receiver, channel_id):
    """The ws client lives in the gateway container: it has `websockets` and
    sits on the compose network."""
    probe = pathlib.Path(__file__).with_name("ws_probe.py")
    ctx = json.dumps(
        {
            "sender": sender,
            "receiver": receiver,
            "channel_id": channel_id,
            "text": f"smoke test {uuid.uuid4().hex[:6]}",
        }
    )
    try:
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "ws_gateway", "python", "-", ctx],
            stdin=probe.open("rb"),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("  SKIP  websocket round trip (docker CLI not found)")
        return

    print(result.stdout.rstrip() or "  FAIL  websocket probe produced no output")
    if result.returncode != 0:
        FAILURES.append(f"websocket round trip failed: {result.stderr[-500:]}")


print("== auth ==")
alice = register("alice")
bob = register("bob")
carol = register("carol")
check("registered three users", all(u["id"] for u in (alice, bob, carol)))

print("== unauthenticated routes are closed ==")
status, _ = call("GET", f"/users/?user_id={bob['id']}")
check("GET /users/ requires auth", status == 401, f"got {status}")
status, _ = call("POST", "/users/bulk", {"ids": [bob["id"]]})
check("POST /users/bulk requires auth", status == 401, f"got {status}")

print("== friend requests ==")
status, _ = call(
    "POST",
    f"/friendship/friends/request?to_username={bob['username']}",
    token=alice["token"],
    expect=201,
)
check("alice -> bob request created", status == 201)

status, _ = call(
    "POST",
    f"/friendship/friends/request?to_username={bob['username']}",
    token=alice["token"],
)
check("duplicate request rejected", status == 409, f"got {status}")

status, _ = call(
    "POST",
    f"/friendship/friends/request?to_username={alice['username']}",
    token=bob["token"],
)
check("reverse duplicate rejected", status == 409, f"got {status}")

status, _ = call(
    "POST",
    f"/friendship/friends/request?to_username={alice['username']}",
    token=alice["token"],
)
check("self request rejected", status == 409, f"got {status}")

status, bob_requests = call(
    "GET", "/friendship/friends/request/me", token=bob["token"], expect=200
)
check("bob sees one request", len(bob_requests or []) == 1, str(bob_requests))

status, accepted = call(
    "POST",
    f"/friendship/friends/request/{bob_requests[0]['id']}/accept",
    token=bob["token"],
    expect=200,
)
check(
    "accept returns friend_id + dm_channel_id",
    isinstance(accepted, dict)
    and accepted.get("friend_id") == alice["id"]
    and "dm_channel_id" in accepted,
    str(accepted),
)
dm_channel_id = (accepted or {}).get("dm_channel_id")

status, alice_channels = call("GET", "/channels/me", token=alice["token"], expect=200)
check(
    "dm channel visible to alice",
    any(c["id"] == dm_channel_id for c in alice_channels or []),
    str(alice_channels),
)

status, friends = call("GET", "/friendship/friends/me", token=bob["token"], expect=200)
check("bob has one friend", len(friends or []) == 1, str(friends))

print("== channel membership authz ==")
status, _ = call("GET", f"/channels/{dm_channel_id}", token=alice["token"], expect=200)
check("member can read channel", status == 200, f"got {status}")
status, _ = call("GET", f"/channels/{dm_channel_id}", token=carol["token"])
check("non-member cannot read channel", status == 404, f"got {status}")

print("== guilds ==")
status, guild = call(
    "POST",
    "/guilds/",
    {"name": "Rainforest", "description": "smoke test guild"},
    token=alice["token"],
    expect=201,
)
guild_id = (guild or {}).get("id")
check("guild created", bool(guild_id), str(guild))

status, alice_channels = call("GET", "/channels/me", token=alice["token"], expect=200)
default_channels = [c for c in alice_channels or [] if c.get("guild_id") == guild_id]
check(
    "default text + voice channels created",
    sorted(c["name"] for c in default_channels) == ["general-text", "general-voice"],
    str(default_channels),
)

status, _ = call("GET", f"/guilds/{guild_id}", token=alice["token"], expect=200)
check("member can read guild", status == 200, f"got {status}")
status, _ = call("GET", f"/guilds/{guild_id}", token=carol["token"])
check("non-member cannot read guild", status == 404, f"got {status}")
status, _ = call("GET", f"/guilds/{guild_id}")
check("anonymous cannot read guild", status == 401, f"got {status}")

print("== guild channel creation ==")
status, new_channel = call(
    "POST",
    f"/channels/guild/{guild_id}",
    {"name": "announcements", "type": "guild_text"},
    token=alice["token"],
    expect=201,
)
check("admin creates guild channel", status == 201, str(new_channel))

status, _ = call(
    "POST",
    f"/channels/guild/{guild_id}",
    {"name": "sneaky", "type": "guild_text"},
    token=carol["token"],
)
check("non-admin cannot create guild channel", status == 403, f"got {status}")

print("== guild invite ==")
status, invite = call(
    "POST",
    f"/guilds/{guild_id}/invite",
    {"user_id": bob["id"]},
    token=alice["token"],
    expect=201,
)
invite_id = (invite or {}).get("invite_id")
check("invite created", bool(invite_id), str(invite))

status, _ = call(
    "POST", f"/guilds/{guild_id}/invite", {"user_id": bob["id"]}, token=alice["token"]
)
check("duplicate invite rejected", status == 409, f"got {status}")

status, member = call(
    "POST",
    f"/guilds/{guild_id}/invites/{invite_id}/accept",
    token=bob["token"],
    expect=201,
)
check("invite accepted", status == 201, str(member))

status, bob_channels = call("GET", "/channels/me", token=bob["token"], expect=200)
bob_guild_channels = sorted(
    c["name"] for c in bob_channels or [] if c.get("guild_id") == guild_id
)
check(
    "invitee joined all guild channels",
    bob_guild_channels == ["announcements", "general-text", "general-voice"],
    str(bob_guild_channels),
)

status, _ = call(
    "POST", f"/guilds/{guild_id}/invites/{invite_id}/accept", token=bob["token"]
)
check("invite is single use", status == 404, f"got {status}")

print("== remove member ==")
status, _ = call(
    "DELETE",
    f"/guilds/{guild_id}/members/{bob['id']}",
    token=alice["token"],
    expect=204,
)
check("admin removed member", status == 204, f"got {status}")

status, bob_channels = call("GET", "/channels/me", token=bob["token"], expect=200)
check(
    "removed member lost guild channels",
    not [c for c in bob_channels or [] if c.get("guild_id") == guild_id],
    str(bob_channels),
)
check(
    "removed member keeps dm channel",
    any(c["id"] == dm_channel_id for c in bob_channels or []),
    str(bob_channels),
)

print("== websocket round trip ==")
run_websocket_probe(alice, bob, dm_channel_id)

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S):")
    for failure in FAILURES:
        print(" -", failure)
    sys.exit(1)
print("ALL CHECKS PASSED")
