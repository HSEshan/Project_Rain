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


def psql(statement: str) -> bool:
    """Run SQL against the dev database, for row shapes REST cannot create.

    Returns False (and skips the caller's check) when the docker CLI is absent,
    the same way `run_probe` degrades.
    """
    try:
        result = subprocess.run(
            [
                "docker", "compose", "exec", "-T", "postgres",
                "psql", "-U", "superuser", "-d", "devdb", "-c", statement,
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("  SKIP  sql fixture (docker CLI not found)")
        return False

    if result.returncode != 0:
        FAILURES.append(f"psql failed: {result.stderr[-400:]}")
        return False
    return True


def run_probe(script_name: str, ctx: dict, label: str):
    """Websocket clients live in the gateway container: it has `websockets` and
    sits on the compose network."""
    probe = pathlib.Path(__file__).with_name(script_name)
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "ws_gateway",
                "python",
                "-",
                json.dumps(ctx),
            ],
            stdin=probe.open("rb"),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(f"  SKIP  {label} (docker CLI not found)")
        return

    print(result.stdout.rstrip() or f"  FAIL  {label} produced no output")
    if result.returncode != 0:
        FAILURES.append(f"{label} failed: {result.stderr[-800:]}")


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

# The invitee has to be able to find the invite after a reload, not only catch
# the realtime event
status, pending = call("GET", "/guilds/invites/me", token=bob["token"], expect=200)
check(
    "invitee can list the pending invite",
    [i["invite_id"] for i in pending or []] == [invite_id]
    # carries the guild name so the list needs no second round trip
    and (pending or [{}])[0].get("guild_name") == "Rainforest",
    str(pending),
)
check(
    "pending invite names the inviter",
    (pending or [{}])[0].get("inviter_id") == alice["id"]
    and (pending or [{}])[0].get("inviter_username") == alice["username"],
    str(pending),
)
status, pending = call("GET", "/guilds/invites/me", token=carol["token"], expect=200)
check("invites are per user", pending == [], str(pending))

status, member = call(
    "POST",
    f"/guilds/{guild_id}/invites/{invite_id}/accept",
    token=bob["token"],
    expect=201,
)
check("invite accepted", status == 201, str(member))

status, pending = call("GET", "/guilds/invites/me", token=bob["token"], expect=200)
check("accepting clears the pending invite", pending == [], str(pending))

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

# The UI invites by username — a person types a name, not a uuid
status, by_name = call(
    "POST",
    f"/guilds/{guild_id}/invite",
    {"username": carol["username"]},
    token=alice["token"],
    expect=201,
)
check("invite by username", status == 201, str(by_name))

status, body = call(
    "POST", f"/guilds/{guild_id}/invite", {"username": "no_such_user"},
    token=alice["token"],
)
check("invite to an unknown username is 404", status == 404, f"got {status}")

status, body = call(
    "POST",
    f"/guilds/{guild_id}/invite",
    {"username": carol["username"], "user_id": carol["id"]},
    token=alice["token"],
)
check("invite must name the user exactly once", status == 422, f"got {status}")

status, body = call("POST", f"/guilds/{guild_id}/invite", {}, token=alice["token"])
check("invite with no target is rejected", status == 422, f"got {status}")

print("== decline invite ==")
# Carol is holding the invite created by username just above
status, pending = call("GET", "/guilds/invites/me", token=carol["token"], expect=200)
carol_invite_id = (pending or [{}])[0].get("invite_id")
check("invitee sees the invite before declining", bool(carol_invite_id), str(pending))

status, _ = call(
    "DELETE",
    f"/guilds/{guild_id}/invites/{carol_invite_id}",
    token=alice["token"],
)
check("only the recipient can decline an invite", status == 403, f"got {status}")

status, _ = call(
    "DELETE",
    f"/guilds/{guild_id}/invites/{carol_invite_id}",
    token=carol["token"],
    expect=204,
)
check("invitee declined the invite", status == 204, f"got {status}")

status, pending = call("GET", "/guilds/invites/me", token=carol["token"], expect=200)
check("declining clears the pending invite", pending == [], str(pending))

# Declining must not join the guild — that is the whole point of the button
status, carol_guilds = call("GET", "/guilds/me", token=carol["token"], expect=200)
check(
    "declining does not join the guild",
    not [g for g in carol_guilds or [] if g["id"] == guild_id],
    str(carol_guilds),
)

status, _ = call(
    "DELETE", f"/guilds/{guild_id}/invites/{carol_invite_id}", token=carol["token"]
)
check("declining a consumed invite is 404", status == 404, f"got {status}")

status, _ = call(
    "POST",
    f"/guilds/{guild_id}/invites/{carol_invite_id}/accept",
    token=carol["token"],
)
check("a declined invite cannot be accepted", status == 404, f"got {status}")

# Declining is not permanent — the guild can ask again
status, reinvite = call(
    "POST",
    f"/guilds/{guild_id}/invite",
    {"user_id": carol["id"]},
    token=alice["token"],
    expect=201,
)
check("can be re-invited after declining", status == 201, f"got {status}")

# `inviter_id` is nullable and was not backfilled, so the listing has to outer
# join it. An inner join would hide every invite created before the column —
# which is exactly the row shape this forces.
if psql(
    "UPDATE guild_invites SET inviter_id = NULL WHERE invite_id = "
    f"'{(reinvite or {}).get('invite_id')}'"
):
    status, pending = call("GET", "/guilds/invites/me", token=carol["token"])
    check(
        "an invite with no inviter is still listed",
        [i["invite_id"] for i in pending or []]
        == [(reinvite or {}).get("invite_id")]
        and (pending or [{}])[0].get("inviter_username") is None,
        str(pending),
    )

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
run_probe(
    "ws_probe.py",
    {
        "sender": alice,
        "receiver": bob,
        "channel_id": dm_channel_id,
        "text": f"smoke test {uuid.uuid4().hex[:6]}",
    },
    "websocket round trip",
)

print("== one user, multiple sockets ==")
run_probe(
    "multi_socket_probe.py",
    {
        "sender": alice,
        "receiver": bob,
        "channel_id": dm_channel_id,
        "text": f"multi socket {uuid.uuid4().hex[:6]}",
    },
    "multi socket probe",
)

print("== realtime events from rest mutations ==")
# Fresh users: this probe drives its own friend request and guild join
run_probe(
    "realtime_probe.py",
    {"alice": register("rt_alice"), "bob": register("rt_bob")},
    "realtime probe",
)

print("== voice (livekit sfu) ==")


def livekit_credentials():
    """Read the SFU key pair out of the running rest_api container.

    The voice probe has to sign LiveKit webhooks and server-API calls, and
    rest_api is where that secret already lives — better than teaching the
    smoke test to parse env files it does not own.
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "rest_api", "printenv"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    env = dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )
    secret = env.get("LIVEKIT_API_SECRET")
    return (
        {"key": env.get("LIVEKIT_API_KEY", "devkey"), "secret": secret}
        if secret
        else None
    )


livekit = livekit_credentials()
if not livekit:
    print("  SKIP  voice probe (LIVEKIT_API_SECRET not set on rest_api)")
else:
    run_probe(
        "voice_probe.py",
        {
            "alice": register("v_alice"),
            "bob": register("v_bob"),
            "carol": register("v_carol"),
            "livekit": livekit,
        },
        "voice probe",
    )

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S):")
    for failure in FAILURES:
        print(" -", failure)
    sys.exit(1)
print("ALL CHECKS PASSED")
