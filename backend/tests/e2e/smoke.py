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


def login_form(username, password):
    """POST /auth/login, which takes an OAuth2 password form rather than JSON."""
    form = urllib.parse.urlencode(
        {"username": username, "password": password}
    ).encode()
    req = urllib.request.Request(BASE + "/auth/login", data=form, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")


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
# A fourth, who is nobody's friend to begin with: the group DM rules are about
# who you are *not* allowed to pull into a room.
dave = register("dave")
check("registered three users", all(u["id"] for u in (alice, bob, carol)))

print("== unauthenticated routes are closed ==")
status, _ = call("GET", f"/users/?user_id={bob['id']}")
check("GET /users/ requires auth", status == 401, f"got {status}")
status, _ = call("POST", "/users/bulk", {"ids": [bob["id"]]})
check("POST /users/bulk requires auth", status == 401, f"got {status}")

print("== auth failures say what went wrong ==")
# The frontend renders these verbatim. They were unreachable for a while: the
# api client caught the axios error and rethrew a bare Error, so every failure
# here reached the user as "Cannot reach the server". These assertions are
# about the *shape* the client depends on, not just the status code.

status, body = call(
    "POST",
    "/auth/register",
    {
        "username": alice["username"],
        "email": f"different_{uuid.uuid4().hex[:8]}@example.com",
        "password": "Passw0rd!23",
    },
)
check("duplicate username is 409", status == 409, f"got {status}")
check(
    "duplicate username says which field",
    isinstance((body or {}).get("detail"), str)
    and "username" in body["detail"].lower(),
    str(body),
)

status, body = call(
    "POST",
    "/auth/register",
    {
        "username": f"different_{uuid.uuid4().hex[:8]}",
        "email": f"{alice['username']}@example.com",
        "password": "Passw0rd!23",
    },
)
check("duplicate email is 409", status == 409, f"got {status}")
check(
    "duplicate email says which field",
    isinstance((body or {}).get("detail"), str) and "email" in body["detail"].lower(),
    str(body),
)

weak = f"weak_{uuid.uuid4().hex[:8]}"
status, body = call(
    "POST",
    "/auth/register",
    # A password made of a word that appears in no error message, so the
    # "does not echo it back" check below cannot pass by coincidence.
    {"username": weak, "email": f"{weak}@example.com", "password": "sentinelvalue"},
)
check("a weak password is 422", status == 422, f"got {status}")
password_errors = [
    error
    for error in (body or {}).get("detail", [])
    if isinstance(error, dict) and error.get("loc", [])[-1:] == ["password"]
]
check("the 422 names the password field", len(password_errors) == 1, str(body))
message = (password_errors or [{}])[0].get("msg", "")
check(
    "the password message is a sentence, not a stringified list",
    "['" not in message and "']" not in message,
    message,
)
check(
    "the password message names every missing requirement",
    all(
        requirement in message
        for requirement in ("uppercase letter", "number", "special character")
    ),
    message,
)

# The submitted value used to come back in `input`, which for this route is a
# plaintext password in an error body. `validation_error_handler` drops it.
check(
    "the 422 does not echo the password back",
    "sentinelvalue" not in json.dumps(body),
    str(body),
)

status, body = call(
    "POST",
    "/auth/register",
    {"username": "no spaces allowed!", "email": "not-an-email", "password": "short"},
)
fields = [
    error.get("loc", [])[-1]
    for error in (body or {}).get("detail", [])
    if isinstance(error, dict)
]
check(
    "every bad field is reported at once, not one per attempt",
    sorted(fields) == ["email", "password", "username"],
    str(fields),
)

# Sign-in answers the same way whether the account exists or the password is
# wrong. Two answers let anyone submit an email and read the status code to
# find out who has an account here.
unknown_status, unknown_body = login_form("nobody@nowhere.example", "Passw0rd!23")
wrong_status, wrong_body = login_form(
    f"{alice['username']}@example.com", "Wr0ng!pass"
)
check("an unknown account is 401", unknown_status == 401, f"got {unknown_status}")
check("a wrong password is 401", wrong_status == 401, f"got {wrong_status}")
check(
    "an unknown account and a wrong password are indistinguishable",
    unknown_body == wrong_body,
    f"{unknown_body} != {wrong_body}",
)

print("== refresh tokens ==")
# Phase 15. The rules being checked are the ones that make rotation worth
# having rather than a longer login: the refresh token is unreadable to the
# page, it is spent exactly once, replaying a spent one kills the session, and
# signing out actually revokes something.


def session_call(path, cookie=None, form=None):
    """A request that can carry and read cookies, which `call` cannot.

    Returns (status, parsed body, list of Set-Cookie header values).
    """
    data = urllib.parse.urlencode(form).encode() if form is not None else None
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    if form is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    else:
        # urllib sends no body for POST without data unless asked
        req.add_header("Content-Length", "0")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req) as resp:
            status, payload, headers = resp.status, resp.read().decode(), resp.headers
    except urllib.error.HTTPError as e:
        status, payload, headers = e.code, e.read().decode(), e.headers
    try:
        parsed = json.loads(payload) if payload else None
    except json.JSONDecodeError:
        parsed = payload
    return status, parsed, headers.get_all("Set-Cookie") or []


REFRESH_COOKIE = "rain_refresh"


def refresh_set_cookie(set_cookies):
    for value in set_cookies:
        if value.startswith(f"{REFRESH_COOKIE}="):
            return value
    return None


def cookie_value(set_cookie):
    return set_cookie.split(";")[0].split("=", 1)[1] if set_cookie else None


def as_request_cookie(set_cookie):
    return set_cookie.split(";")[0] if set_cookie else None


s_user = f"sess_{uuid.uuid4().hex[:8]}"
s_password = "Passw0rd!23"
call(
    "POST",
    "/auth/register",
    {"username": s_user, "email": f"{s_user}@example.com", "password": s_password},
    expect=201,
)

status, body, set_cookies = session_call(
    "/auth/login", form={"username": f"{s_user}@example.com", "password": s_password}
)
login_cookie = refresh_set_cookie(set_cookies)
check("sign-in returns an access token", status == 200 and "access_token" in (body or {}), str(body))
check("sign-in sets a refresh cookie", login_cookie is not None, str(set_cookies))
check(
    "the refresh cookie is httponly, so the page cannot read it",
    "httponly" in (login_cookie or "").lower(),
    login_cookie or "",
)
check(
    "the refresh cookie is scoped to the auth routes",
    "path=/api/auth" in (login_cookie or "").lower(),
    login_cookie or "",
)
hint_cookie = next(
    (c for c in set_cookies if c.startswith("rain_session=")), None
)
check(
    "sign-in also sets a readable session marker",
    hint_cookie is not None,
    "without it every anonymous page load sends a refresh request",
)
check(
    "the marker is readable and carries nothing",
    hint_cookie is not None
    and "httponly" not in hint_cookie.lower()
    and cookie_value(hint_cookie) == "1",
    hint_cookie or "",
)
check(
    "the refresh token is not in the response body",
    cookie_value(login_cookie) not in json.dumps(body or {}),
    "the token the browser must keep private was also returned in the body",
)

first_access = (body or {}).get("access_token")
status, refreshed, set_cookies = session_call(
    "/auth/refresh", cookie=as_request_cookie(login_cookie)
)
second_cookie = refresh_set_cookie(set_cookies)
check("refresh returns a new access token", status == 200, f"got {status} {refreshed}")
check(
    "the access token from a refresh works",
    call("GET", "/channels/me", token=(refreshed or {}).get("access_token"))[0] == 200,
)
check("refresh rotates the cookie", second_cookie is not None, str(set_cookies))
check(
    "the rotated refresh token is a different token",
    cookie_value(second_cookie) != cookie_value(login_cookie),
    "the same refresh token came back, so nothing was rotated",
)
check(
    "the rotated cookie keeps the family's expiry rather than extending it",
    # A successor inherits `expires_at`, which is what makes the 30 days an
    # absolute session lifetime instead of an idle timeout.
    "expires=" in (second_cookie or "").lower(),
    second_cookie or "",
)

# Replaying the token that was just spent. Inside the grace window this is two
# tabs waking together, not theft, and the session must survive it.
status, _, grace_cookies = session_call(
    "/auth/refresh", cookie=as_request_cookie(login_cookie)
)
check(
    "replaying a just-rotated token inside the grace window is served, not punished",
    status == 200,
    f"got {status}: two tabs refreshing at once would sign the user out",
)
grace_cookie = refresh_set_cookie(grace_cookies) or second_cookie

# The same replay, aged past the grace window. Backdating in the database is
# the only way to test this without sleeping through it in CI.
if psql(
    "UPDATE refresh_tokens SET revoked_at = now() - interval '1 hour' "
    "WHERE revoked_at IS NOT NULL AND user_id = "
    f"(SELECT id FROM users WHERE username = '{s_user}')"
):
    status, _, _ = session_call("/auth/refresh", cookie=as_request_cookie(login_cookie))
    check("replaying a long-spent token is refused", status == 401, f"got {status}")

    status, _, _ = session_call(
        "/auth/refresh", cookie=as_request_cookie(grace_cookie)
    )
    check(
        "reuse revokes the whole family, not just the replayed token",
        status == 401,
        f"got {status}: the live token survived a detected replay",
    )

# A fresh session, to check that signing out ends one.
status, body, set_cookies = session_call(
    "/auth/login", form={"username": f"{s_user}@example.com", "password": s_password}
)
logout_cookie = refresh_set_cookie(set_cookies)
status, _, cleared = session_call(
    "/auth/logout", cookie=as_request_cookie(logout_cookie)
)
check("logout is 204", status == 204, f"got {status}")
check(
    "logout clears the cookie",
    "max-age=0" in (refresh_set_cookie(cleared) or "").lower(),
    str(cleared),
)
status, _, _ = session_call("/auth/refresh", cookie=as_request_cookie(logout_cookie))
check(
    "a signed-out session cannot be refreshed",
    status == 401,
    f"got {status}: sign-out did not revoke anything server-side",
)

status, _, _ = session_call("/auth/refresh")
check("refresh without a cookie is 401", status == 401, f"got {status}")

status, _, demo_cookies = session_call("/demo/login")
if status == 200:
    check(
        "the demo session gets a refresh cookie too",
        refresh_set_cookie(demo_cookies) is not None,
        str(demo_cookies),
    )
else:
    print("  SKIP  demo refresh cookie (DEMO_ENABLED is off)")

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
check("non-member cannot create guild channel", status == 404, f"got {status}")

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

print("== profile card ==")
status, profile = call("GET", f"/users/{bob['id']}/profile", token=alice["token"])
check("profile readable", status == 200, str(profile))

# The regression that opened this section. `GET /users/` returned the ORM row
# with no response model, so any authenticated user could read anyone's email
# and bcrypt hash. Both routes now declare one; these two checks are the reason
# they may never stop declaring one.
check("profile hides the email", "email" not in (profile or {}), str(profile))
check("profile hides the password hash", "password_hash" not in (profile or {}))
status, plain = call("GET", f"/users/?user_id={bob['id']}", token=alice["token"])
check("GET /users/ hides the email", "email" not in (plain or {}), str(plain))
check("GET /users/ hides the password hash", "password_hash" not in (plain or {}))

check(
    "friends see each other as friends",
    (profile or {}).get("friend_state") == "friends",
    str(profile),
)
check(
    "the profile points at the existing dm",
    (profile or {}).get("dm_channel_id") == dm_channel_id,
    str(profile),
)
# A guild of their own, because bob was removed from Rainforest a few checks
# ago. That is itself the interesting half: a guild you were removed from must
# stop being mutual.
check(
    "a guild you were removed from is not mutual",
    (profile or {}).get("mutual_guilds") == [],
    str(profile),
)
status, shared_guild = call(
    "POST",
    "/guilds/",
    {"name": "Profile Guild", "description": "for the card"},
    token=alice["token"],
    expect=201,
)
status, shared_invite = call(
    "POST",
    f"/guilds/{shared_guild['id']}/invite",
    {"user_id": bob["id"]},
    token=alice["token"],
    expect=201,
)
call(
    "POST",
    f"/guilds/{shared_guild['id']}/invites/{shared_invite['invite_id']}/accept",
    token=bob["token"],
    expect=201,
)
status, profile = call("GET", f"/users/{bob['id']}/profile", token=alice["token"])
check(
    "mutual guilds are listed",
    [g["name"] for g in (profile or {}).get("mutual_guilds", [])] == ["Profile Guild"],
    str(profile),
)

status, own = call("GET", f"/users/{alice['id']}/profile", token=alice["token"])
check("your own profile says so", (own or {}).get("friend_state") == "self", str(own))

status, stranger = call("GET", f"/users/{carol['id']}/profile", token=alice["token"])
check(
    "a stranger is a stranger",
    (stranger or {}).get("friend_state") == "none"
    and (stranger or {}).get("dm_channel_id") is None
    and (stranger or {}).get("mutual_guilds") == [],
    str(stranger),
)

status, _ = call("GET", f"/users/{uuid.uuid4()}/profile", token=alice["token"])
check("unknown user is 404", status == 404, f"got {status}")
status, _ = call("GET", f"/users/{bob['id']}/profile")
check("profile requires auth", status == 401, f"got {status}")

print("== profile bio ==")
# Phase 16. The first route where a user edits themselves, so the checks are as
# much about what it refuses as what it stores.

status, profile = call("GET", f"/users/{alice['id']}/profile", token=alice["token"])
check(
    "a new account has no bio, and null is what that looks like",
    status == 200 and (profile or {}).get("bio") is None,
    str(profile),
)

status, updated = call(
    "PATCH", "/users/me", {"bio": "Builds things and breaks them."},
    token=alice["token"], expect=200,
)
check(
    "PATCH /users/me returns the updated profile",
    (updated or {}).get("bio") == "Builds things and breaks them.",
    str(updated),
)
check(
    "the update response is a full profile, not a fragment",
    (updated or {}).get("friend_state") == "self"
    and "created_at" in (updated or {}),
    str(updated),
)

status, seen = call("GET", f"/users/{alice['id']}/profile", token=bob["token"])
check(
    "another person sees the bio",
    (seen or {}).get("bio") == "Builds things and breaks them.",
    str(seen),
)
check("the bio route still hides the email", "email" not in (seen or {}), str(seen))

# A PATCH that does not mention the bio must not erase it. The whole reason the
# service reads `model_fields_set` rather than trusting pydantic's default.
status, untouched = call("PATCH", "/users/me", {}, token=alice["token"], expect=200)
check(
    "a patch that names no field changes nothing",
    (untouched or {}).get("bio") == "Builds things and breaks them.",
    str(untouched),
)

status, whitespace = call(
    "PATCH", "/users/me", {"bio": "  padded  \n\n\n\n  and spaced  "},
    token=alice["token"], expect=200,
)
check(
    "a bio is trimmed and its blank-line runs collapsed",
    (whitespace or {}).get("bio") == "padded\n\nand spaced",
    repr((whitespace or {}).get("bio")),
)

status, stripped = call(
    "PATCH", "/users/me", {"bio": "before‮after\x07"},
    token=alice["token"], expect=200,
)
check(
    "control and direction-override characters are removed",
    (stripped or {}).get("bio") == "beforeafter",
    repr((stripped or {}).get("bio")),
)

status, body = call(
    "PATCH", "/users/me", {"bio": "x" * 191}, token=alice["token"]
)
check("an over-long bio is 422", status == 422, f"got {status}")
message = next(
    (
        error.get("msg", "")
        for error in (body or {}).get("detail", [])
        if isinstance(error, dict) and error.get("loc", [])[-1:] == ["bio"]
    ),
    "",
)
check(
    "the bio message is a sentence naming the limit",
    "190" in message and "['" not in message,
    message,
)
check(
    "the 422 does not echo the bio back",
    "xxxxx" not in json.dumps(body or {}),
    "the rejected value came back in the error body",
)

status, exact = call(
    "PATCH", "/users/me", {"bio": "y" * 190}, token=alice["token"], expect=200
)
check(
    "a bio of exactly the limit is accepted",
    (exact or {}).get("bio") == "y" * 190,
    str(status),
)

status, cleared = call(
    "PATCH", "/users/me", {"bio": "   "}, token=alice["token"], expect=200
)
check(
    "a blank bio clears it rather than storing an empty string",
    (cleared or {}).get("bio") is None,
    repr((cleared or {}).get("bio")),
)
status, cleared = call(
    "PATCH", "/users/me", {"bio": None}, token=alice["token"], expect=200
)
check("an explicit null clears it too", (cleared or {}).get("bio") is None, str(cleared))

status, _ = call("PATCH", "/users/me", {"bio": "anonymous"})
check("PATCH /users/me requires auth", status == 401, f"got {status}")

# There is deliberately no route that edits anyone else, so the closest thing to
# an authz check is that the path cannot name a victim.
status, _ = call(
    "PATCH", f"/users/{bob['id']}", {"bio": "written by alice"}, token=alice["token"]
)
check(
    "there is no route for editing another account",
    status in (404, 405),
    f"got {status}",
)

print("== group dms ==")
# alice is friends with bob already; carol has to be a friend too, because you
# can only put your own friends in a group.
status, _ = call(
    "POST",
    f"/friendship/friends/request?to_username={carol['username']}",
    token=alice["token"],
    expect=201,
)
status, carol_requests = call(
    "GET", "/friendship/friends/request/me", token=carol["token"], expect=200
)
call(
    "POST",
    f"/friendship/friends/request/{carol_requests[0]['id']}/accept",
    token=carol["token"],
    expect=200,
)

status, group = call(
    "POST",
    "/channels/group",
    {"user_ids": [bob["id"], carol["id"]], "name": "Smoke crew"},
    token=alice["token"],
    expect=201,
)
group_id = (group or {}).get("id")
check("group dm created", status == 201, str(group))
check("group dm has its own type", (group or {}).get("type") == "group_dm", str(group))
check(
    "the creator owns it", (group or {}).get("owner_id") == alice["id"], str(group)
)

status, members = call("GET", f"/channels/{group_id}/members", token=bob["token"])
member_ids = [m["user_id"] for m in (members or {}).get("members", [])]
check("everyone is in it", sorted(member_ids) == sorted(
    [alice["id"], bob["id"], carol["id"]]
), str(members))
check(
    "exactly one owner, and it is the creator",
    [m["user_id"] for m in (members or {}).get("members", []) if m["is_owner"]]
    == [alice["id"]],
    str(members),
)

status, carol_channels = call("GET", "/channels/me", token=carol["token"], expect=200)
check(
    "a group dm shows up in its members' channels",
    any(c["id"] == group_id for c in carol_channels or []),
    str(carol_channels),
)

# The rule that keeps a group DM from being a way to corner strangers
status, body = call(
    "POST",
    "/channels/group",
    {"user_ids": [dave["id"], bob["id"]]},
    token=alice["token"],
)
check("cannot open a group with a non-friend", status == 403, f"got {status} {body}")
status, _ = call(
    "POST", "/channels/group", {"user_ids": [bob["id"]]}, token=alice["token"]
)
check("a group needs more than one other person", status == 422, f"got {status}")
status, _ = call(
    "POST", "/channels/group", {"user_ids": [bob["id"], bob["id"]]}, token=alice["token"]
)
check("the same person twice is rejected", status == 422, f"got {status}")
status, _ = call(
    "POST",
    "/channels/group",
    {"user_ids": [bob["id"], alice["id"]]},
    token=alice["token"],
)
check("you are already in your own group", status == 400, f"got {status}")

status, body = call(
    "POST", f"/channels/{group_id}/members", {"user_id": dave["id"]}, token=alice["token"]
)
check("cannot add a non-friend later either", status == 403, f"got {status} {body}")

# ...but anyone in the group may add one of *their* friends
status, _ = call(
    "POST",
    f"/friendship/friends/request?to_username={dave['username']}",
    token=bob["token"],
    expect=201,
)
status, dave_requests = call(
    "GET", "/friendship/friends/request/me", token=dave["token"], expect=200
)
call(
    "POST",
    f"/friendship/friends/request/{dave_requests[0]['id']}/accept",
    token=dave["token"],
    expect=200,
)
status, roster = call(
    "POST", f"/channels/{group_id}/members", {"user_id": dave["id"]}, token=bob["token"]
)
check("any member can add their own friend", status == 201, f"got {status} {roster}")
check("the new roster comes back", len((roster or {}).get("members", [])) == 4, str(roster))

status, _ = call(
    "POST", f"/channels/{group_id}/members", {"user_id": dave["id"]}, token=bob["token"]
)
check("adding someone twice is 409", status == 409, f"got {status}")

status, renamed = call(
    "PATCH", f"/channels/{group_id}", {"name": "Renamed crew"}, token=carol["token"]
)
check(
    "any member can rename the group",
    status == 200 and (renamed or {}).get("name") == "Renamed crew",
    f"{status} {renamed}",
)

# None of this applies to a two-person DM, which has no roster to manage
status, _ = call("PATCH", f"/channels/{dm_channel_id}", {"name": "no"}, token=alice["token"])
check("a two-person dm cannot be renamed", status == 403, f"got {status}")
status, _ = call(
    "DELETE", f"/channels/{dm_channel_id}/members/me", token=alice["token"]
)
check("a two-person dm cannot be left", status == 403, f"got {status}")

status, _ = call(
    "DELETE", f"/channels/{group_id}/members/me", token=alice["token"], expect=204
)
check("the owner can leave", status == 204, f"got {status}")
status, members = call("GET", f"/channels/{group_id}/members", token=bob["token"])
check(
    "ownership moves to the longest-standing member left",
    [m["user_id"] for m in (members or {}).get("members", []) if m["is_owner"]]
    == [bob["id"]],
    str(members),
)
status, _ = call("GET", f"/channels/{group_id}/members", token=alice["token"])
check("leaving takes your access with it", status == 404, f"got {status}")

for departing in (bob, carol, dave):
    call("DELETE", f"/channels/{group_id}/members/me", token=departing["token"])
status, _ = call("GET", f"/channels/{group_id}", token=bob["token"])
check("the last one out deletes the group", status == 404, f"got {status}")

print("== dm calls ==")
status, session = call(
    "POST", f"/channels/{dm_channel_id}/voice/join", token=alice["token"]
)
check("a dm accepts a call", status == 200 and bool((session or {}).get("token")), str(status))
check(
    "the call room is the dm channel",
    (session or {}).get("room") == dm_channel_id,
    str(session)[:120],
)

status, callable_group = call(
    "POST",
    "/channels/group",
    {"user_ids": [bob["id"], carol["id"]]},
    token=alice["token"],
    expect=201,
)
status, session = call(
    "POST",
    f"/channels/{(callable_group or {}).get('id')}/voice/join",
    token=carol["token"],
)
check("a group dm accepts a call", status == 200 and bool((session or {}).get("token")), str(status))

status, roster = call(
    "GET", f"/channels/{dm_channel_id}/voice/participants", token=bob["token"]
)
check("the other side can read the call roster", status == 200, str(roster))

status, _ = call("POST", f"/channels/{dm_channel_id}/voice/join", token=dave["token"])
check("a non-member cannot call", status == 404, f"got {status}")

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

print("== guild roles ==")
# Fresh users and a fresh guild: this section kicks, demotes and deletes.
owner = register("gr_owner")
admin = register("gr_admin")
admin2 = register("gr_admin2")
mod = register("gr_mod")
member = register("gr_member")
outsider = register("gr_out")

status, roles_guild = call(
    "POST", "/guilds/", {"name": "Roles", "description": "roles"}, token=owner["token"]
)
rg = roles_guild["id"]


def join(person, guild_id=None, inviter=None):
    guild_id = guild_id or rg
    _, invite = call(
        "POST",
        f"/guilds/{guild_id}/invite",
        {"user_id": person["id"]},
        token=(inviter or owner)["token"],
    )
    call(
        "POST",
        f"/guilds/{guild_id}/invites/{invite['invite_id']}/accept",
        token=person["token"],
    )


def set_role(actor, target, role, guild_id=None):
    return call(
        "PATCH",
        f"/guilds/{guild_id or rg}/members/{target['id']}",
        {"role": role},
        token=actor["token"],
    )


def roster(guild_id=None):
    _, rows = call("GET", f"/guilds/{guild_id or rg}/members", token=owner["token"])
    return {row["user_id"]: row["role"] for row in rows or []}


for person in (admin, admin2, mod, member):
    join(person)

status, body = set_role(member, mod, "moderator")
check("a member cannot change roles (403)", status == 403, f"{status} {body}")
status, body = set_role(outsider, mod, "moderator")
check("a non-member cannot change roles (404)", status == 404, f"{status} {body}")

status, body = set_role(owner, admin, "admin")
check(
    "the owner can make an admin",
    status == 200 and (body or {}).get("role") == "admin",
    f"{status} {body}",
)
status, body = set_role(admin, mod, "moderator")
check(
    "an admin can make a moderator",
    status == 200 and (body or {}).get("role") == "moderator",
    f"{status} {body}",
)
status, body = set_role(admin, admin2, "admin")
check("an admin can make another admin", status == 200, f"{status} {body}")

status, body = set_role(mod, member, "moderator")
check("a moderator cannot change roles (403)", status == 403, f"{status} {body}")
status, body = set_role(admin, admin, "member")
check("nobody can change their own role (403)", status == 403, f"{status} {body}")
status, body = set_role(member, member, "admin")
check("a member cannot promote themselves (403)", status == 403, f"{status} {body}")
status, body = set_role(admin, admin2, "member")
check("an admin cannot demote an equal (403)", status == 403, f"{status} {body}")
status, body = set_role(admin, owner, "member")
check("an admin cannot demote the owner (403)", status == 403, f"{status} {body}")
status, body = set_role(owner, owner, "member")
check("the owner cannot demote themselves (403)", status == 403, f"{status} {body}")
status, body = set_role(owner, outsider, "member")
check("a role for a non-member is a 404", status == 404, f"{status} {body}")
status, body = set_role(owner, member, "superuser")
check("an unknown role is a 422", status == 422, f"{status} {body}")

rows = roster()
check(
    "refused role changes changed nothing",
    rows.get(owner["id"]) == "admin"
    and rows.get(admin["id"]) == "admin"
    and rows.get(admin2["id"]) == "admin"
    and rows.get(mod["id"]) == "moderator"
    and rows.get(member["id"]) == "member",
    str(rows),
)
status, rows = call("GET", f"/guilds/{rg}/members", token=member["token"])
check(
    "the member list is allowlisted",
    status == 200 and set((rows or [{}])[0]) == {"guild_id", "user_id", "status", "role"},
    str((rows or [{}])[0]),
)

print("== guild update ==")
status, body = call("PATCH", f"/guilds/{rg}", {"name": "Nope"}, token=member["token"])
check("a member cannot rename the guild (403)", status == 403, f"{status} {body}")
status, body = call("PATCH", f"/guilds/{rg}", {"name": "Nope"}, token=mod["token"])
check("a moderator cannot rename the guild (403)", status == 403, f"{status} {body}")
status, body = call("PATCH", f"/guilds/{rg}", {"name": "Nope"}, token=outsider["token"])
check("a non-member cannot rename the guild (404)", status == 404, f"{status} {body}")

status, body = call(
    "PATCH", f"/guilds/{rg}", {"name": "  Renamed  "}, token=admin["token"]
)
check(
    "an admin can rename, and the name is trimmed",
    status == 200 and (body or {}).get("name") == "Renamed",
    f"{status} {body}",
)
check(
    "a rename leaves the description alone",
    (body or {}).get("description") == "roles",
    str(body),
)
status, body = call(
    "PATCH", f"/guilds/{rg}", {"description": "changed"}, token=owner["token"]
)
check(
    "a description edit leaves the name alone",
    status == 200
    and (body or {}).get("name") == "Renamed"
    and (body or {}).get("description") == "changed",
    f"{status} {body}",
)
status, body = call("PATCH", f"/guilds/{rg}", {"name": "   "}, token=owner["token"])
check("a blank name is a 422", status == 422, f"{status} {body}")
status, body = call("PATCH", f"/guilds/{rg}", {"name": None}, token=owner["token"])
check("a null name is a 422", status == 422, f"{status} {body}")
status, body = call("PATCH", f"/guilds/{rg}", {"name": "x" * 101}, token=owner["token"])
check("an over-long name is a 422", status == 422, f"{status} {body}")
status, body = call(
    "PATCH", f"/guilds/{rg}", {"description": "x" * 301}, token=owner["token"]
)
check("an over-long description is a 422", status == 422, f"{status} {body}")
status, body = call("POST", "/guilds/", {"name": " ", "description": ""}, token=owner["token"])
check("a guild cannot be created with a blank name", status == 422, f"{status} {body}")

print("== guild channel delete ==")
status, doomed = call(
    "POST",
    f"/channels/guild/{rg}",
    {"name": "doomed", "type": "guild_text"},
    token=admin["token"],
)
check("an admin can create a channel", status == 201, str(doomed))
status, body = call(
    "POST",
    f"/channels/guild/{rg}",
    {"name": "nope", "type": "guild_text"},
    token=mod["token"],
)
check("a moderator cannot create a channel (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/channels/{doomed['id']}", token=member["token"])
check("a member cannot delete a channel (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/channels/{doomed['id']}", token=mod["token"])
check("a moderator cannot delete a channel (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/channels/{doomed['id']}", token=outsider["token"])
check("a non-member cannot delete a channel (404)", status == 404, f"{status} {body}")
check(
    "a channel with a message in it can be deleted",
    psql(
        "INSERT INTO messages (id, sender_id, channel_id, content, created_at) VALUES "
        f"(gen_random_uuid(), '{owner['id']}', '{doomed['id']}', 'bye', now())"
    ),
)
status, body = call("DELETE", f"/channels/{doomed['id']}", token=admin["token"])
check("an admin can delete a channel", status == 204, f"{status} {body}")
status, body = call("DELETE", f"/channels/{doomed['id']}", token=admin["token"])
check("deleting it twice is a 404", status == 404, f"{status} {body}")
_, member_channels = call("GET", "/channels/me", token=member["token"])
check(
    "a deleted channel leaves its members' lists",
    doomed["id"] not in [c["id"] for c in member_channels or []],
    str(member_channels),
)
status, body = call("DELETE", f"/channels/{dm_channel_id}", token=alice["token"])
check("a DM cannot be deleted (403)", status == 403, f"{status} {body}")

print("== who is in a channel you are not in ==")
status, seen = call(
    "POST", "/channels/bulk/participants", [dm_channel_id], token=outsider["token"]
)
check("a stranger cannot read a DM's participants", status == 200 and seen == {}, f"{status} {seen}")
status, seen = call("POST", "/channels/bulk/participants", [dm_channel_id], token=alice["token"])
check("a member still can", status == 200 and bool((seen or {}).get(dm_channel_id)), f"{status} {seen}")

print("== kick by rank ==")
victim = register("gr_victim")
join(victim)
status, body = call("DELETE", f"/guilds/{rg}/members/{victim['id']}", token=member["token"])
check("a member cannot remove anyone (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{rg}/members/{admin['id']}", token=mod["token"])
check("a moderator cannot remove an admin (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{rg}/members/{owner['id']}", token=admin["token"])
check("an admin cannot remove the owner (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{rg}/members/{admin2['id']}", token=admin["token"])
check("an admin cannot remove an equal (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{rg}/members/{owner['id']}", token=owner["token"])
check("the owner cannot remove themselves (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{rg}/members/{victim['id']}", token=mod["token"])
check("a moderator can remove a member", status == 204, f"{status} {body}")
check("the removed member is gone", victim["id"] not in roster(), str(roster()))
status, body = call("DELETE", f"/guilds/{rg}/members/{outsider['id']}", token=owner["token"])
check("removing a non-member is a 404", status == 404, f"{status} {body}")

print("== guild delete ==")
status, body = call("DELETE", f"/guilds/{rg}", token=admin["token"])
check("an admin cannot delete the guild (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{rg}", token=outsider["token"])
check("a non-member cannot delete the guild (404)", status == 404, f"{status} {body}")

_, rg_channels = call("GET", "/channels/me", token=member["token"])
rg_channel_ids = [c["id"] for c in rg_channels or [] if c.get("guild_id") == rg]
check("the guild still has channels to delete", len(rg_channel_ids) == 2, str(rg_channel_ids))
check(
    "a guild with a message in it can be deleted",
    psql(
        "INSERT INTO messages (id, sender_id, channel_id, content, created_at) VALUES "
        f"(gen_random_uuid(), '{owner['id']}', '{rg_channel_ids[0]}', 'bye', now())"
    ),
)
call(
    "POST",
    f"/guilds/{rg}/invite",
    {"user_id": outsider["id"]},
    token=owner["token"],
    expect=201,
)
status, body = call("DELETE", f"/guilds/{rg}", token=owner["token"])
check("the owner can delete the guild", status == 204, f"{status} {body}")
status, body = call("GET", f"/guilds/{rg}", token=owner["token"])
check("the deleted guild is gone", status == 404, f"{status} {body}")
_, member_channels = call("GET", "/channels/me", token=member["token"])
check(
    "its channels leave every member's list",
    not [c for c in member_channels or [] if c.get("guild_id") == rg],
    str(member_channels),
)
_, member_guilds = call("GET", "/guilds/me", token=member["token"])
check("it leaves every member's guild list", member_guilds == [], str(member_guilds))
_, pending = call("GET", "/guilds/invites/me", token=outsider["token"])
check("a pending invite goes with it", pending == [], str(pending))

print("== message edit and delete ==")
me_owner, me_admin, me_mod, me_mod2, me_member, me_out = (
    register("me_owner"), register("me_admin"), register("me_mod"),
    register("me_mod2"), register("me_member"), register("me_out"),
)
_, me_guild = call(
    "POST", "/guilds/", {"name": "Edits", "description": ""}, token=me_owner["token"]
)
mg = me_guild["id"]
for person in (me_admin, me_mod, me_mod2, me_member):
    join(person, mg, me_owner)
set_role(me_owner, me_admin, "admin", mg)
set_role(me_owner, me_mod, "moderator", mg)
set_role(me_owner, me_mod2, "moderator", mg)
_, me_channels = call("GET", "/channels/me", token=me_owner["token"])
mc = [c for c in me_channels if c.get("guild_id") == mg and c["type"] == "guild_text"][0]["id"]


def seed_message(author, text="hello", channel=None):
    message_id = str(uuid.uuid4())
    psql(
        "INSERT INTO messages (id, sender_id, channel_id, content, created_at) VALUES "
        f"('{message_id}', '{author['id']}', '{channel or mc}', '{text}', now())"
    )
    return message_id


def in_history(message_id, reader, channel=None):
    _, rows = call("GET", f"/messages/{channel or mc}", token=reader["token"])
    return next((m for m in rows or [] if m["id"] == message_id), None)


mine = seed_message(me_member)
status, body = call("PATCH", f"/messages/{mine}", {"content": "edited"}, token=me_member["token"])
check(
    "an author can edit their message",
    status == 200 and (body or {}).get("content") == "edited" and (body or {}).get("edited_at"),
    f"{status} {body}",
)
row = in_history(mine, me_owner)
check(
    "the edit is in history, marked",
    (row or {}).get("content") == "edited" and (row or {}).get("edited_at"),
    str(row),
)
status, body = call("PATCH", f"/messages/{mine}", {"content": "x"}, token=me_owner["token"])
check("not even the owner can edit someone else's words (403)", status == 403, f"{status} {body}")
status, body = call("PATCH", f"/messages/{mine}", {"content": "x"}, token=me_out["token"])
check("a non-member cannot edit (404)", status == 404, f"{status} {body}")
status, body = call("DELETE", f"/messages/{mine}", token=me_out["token"])
check("a non-member cannot delete (404)", status == 404, f"{status} {body}")
status, body = call("PATCH", f"/messages/{mine}", {"content": "   "}, token=me_member["token"])
check("a text message cannot be edited empty (400)", status == 400, f"{status} {body}")
status, body = call("PATCH", f"/messages/{mine}", {"content": "x" * 4001}, token=me_member["token"])
check("an over-long edit is a 422", status == 422, f"{status} {body}")
status, body = call("PATCH", "/messages/00000000-0000-0000-0000-000000000000", {"content": "x"}, token=me_member["token"])
check("an unknown message is a 404", status == 404, f"{status} {body}")

status, body = call("DELETE", f"/messages/{mine}", token=me_member["token"])
check("an author can delete their message", status == 204, f"{status} {body}")
check("and it is gone", in_history(mine, me_owner) is None)

theirs = seed_message(me_member)
other_member = register("me_other")
join(other_member, mg, me_owner)
status, body = call("DELETE", f"/messages/{theirs}", token=other_member["token"])
check("a member cannot delete another's message (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/messages/{theirs}", token=me_mod["token"])
check("a moderator can delete a member's message", status == 204, f"{status} {body}")

peer = seed_message(me_mod2)
status, body = call("DELETE", f"/messages/{peer}", token=me_mod["token"])
check("a moderator cannot delete a peer's (403)", status == 403, f"{status} {body}")
above = seed_message(me_admin)
status, body = call("DELETE", f"/messages/{above}", token=me_mod["token"])
check("a moderator cannot delete an admin's (403)", status == 403, f"{status} {body}")
owners = seed_message(me_owner)
status, body = call("DELETE", f"/messages/{owners}", token=me_admin["token"])
check("an admin cannot delete the owner's (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/messages/{above}", token=me_owner["token"])
check("the owner can delete an admin's", status == 204, f"{status} {body}")

gone_author = seed_message(other_member)
call("DELETE", f"/guilds/{mg}/members/me", token=other_member["token"])
status, body = call("DELETE", f"/messages/{gone_author}", token=me_mod["token"])
check("a moderator can tidy up after someone who left", status == 204, f"{status} {body}")

dm_message = seed_message(alice, channel=dm_channel_id)
status, body = call("DELETE", f"/messages/{dm_message}", token=bob["token"])
check("in a DM, the other person cannot delete it (403)", status == 403, f"{status} {body}")
status, body = call("PATCH", f"/messages/{dm_message}", {"content": "x"}, token=bob["token"])
check("or edit it (403)", status == 403, f"{status} {body}")

print("== leave and transfer ==")
lt_owner, lt_heir, lt_member, lt_out = (
    register("lt_owner"), register("lt_heir"), register("lt_member"), register("lt_out"),
)
_, lt_guild = call(
    "POST", "/guilds/", {"name": "Heirloom", "description": ""}, token=lt_owner["token"]
)
lg = lt_guild["id"]
join(lt_heir, lg, lt_owner)
join(lt_member, lg, lt_owner)

status, body = call("DELETE", f"/guilds/{lg}/members/me", token=lt_out["token"])
check("a non-member cannot leave (404)", status == 404, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{lg}/members/me", token=lt_owner["token"])
check("the owner cannot leave (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{lg}/members/me", token=lt_member["token"])
check("a member can leave", status == 204, f"{status} {body}")
_, left_channels = call("GET", "/channels/me", token=lt_member["token"])
check(
    "leaving leaves the channels",
    not [c for c in left_channels or [] if c.get("guild_id") == lg],
    str(left_channels),
)
join(lt_member, lg, lt_owner)

status, body = call(
    "POST", f"/guilds/{lg}/transfer", {"user_id": lt_member["id"]}, token=lt_heir["token"]
)
check("a member cannot transfer (403)", status == 403, f"{status} {body}")
call("PATCH", f"/guilds/{lg}/members/{lt_heir['id']}", {"role": "admin"}, token=lt_owner["token"])
status, body = call(
    "POST", f"/guilds/{lg}/transfer", {"user_id": lt_heir["id"]}, token=lt_heir["token"]
)
check("an admin cannot take the guild (403)", status == 403, f"{status} {body}")
status, body = call(
    "POST", f"/guilds/{lg}/transfer", {"user_id": lt_out["id"]}, token=lt_owner["token"]
)
check("it cannot go to a non-member (404)", status == 404, f"{status} {body}")
status, body = call(
    "POST", f"/guilds/{lg}/transfer", {"user_id": lt_owner["id"]}, token=lt_owner["token"]
)
check("it cannot go to its owner (400)", status == 400, f"{status} {body}")
status, body = call(
    "POST", f"/guilds/{lg}/transfer", {"user_id": lt_member["id"]}, token=lt_owner["token"]
)
check(
    "the owner can transfer, even to a plain member",
    status == 200 and (body or {}).get("owner_id") == lt_member["id"],
    f"{status} {body}",
)
_, lg_rows = call("GET", f"/guilds/{lg}/members", token=lt_member["token"])
lg_roles = {row["user_id"]: row["role"] for row in lg_rows or []}
check(
    "the new owner holds the admin row, the old one keeps theirs",
    lg_roles.get(lt_member["id"]) == "admin" and lg_roles.get(lt_owner["id"]) == "admin",
    str(lg_roles),
)
status, body = call("DELETE", f"/guilds/{lg}", token=lt_owner["token"])
check("the old owner can no longer delete it (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{lg}/members/{lt_owner['id']}", token=lt_member["token"])
check("the new owner outranks the old one", status == 204, f"{status} {body}")

print("== invite links ==")
il_owner, il_member, il_a, il_b, il_c = (
    register("il_owner"), register("il_member"), register("il_a"), register("il_b"), register("il_c"),
)
_, il_guild = call(
    "POST", "/guilds/", {"name": "Open Door", "description": "come in"}, token=il_owner["token"]
)
ig = il_guild["id"]
join(il_member, ig, il_owner)

status, link = call("POST", f"/guilds/{ig}/invite-links", {}, token=il_owner["token"])
check(
    "a link can be created",
    status == 201 and len((link or {}).get("code", "")) >= 16,
    f"{status} {link}",
)
code = (link or {}).get("code")
check("with no expiry and no limit by default", link.get("expires_at") is None and link.get("max_uses") is None)
status, body = call("POST", f"/guilds/{ig}/invite-links", {}, token=il_a["token"])
check("a non-member cannot make one (404)", status == 404, f"{status} {body}")
status, body = call("POST", f"/guilds/{ig}/invite-links", {"max_uses": 0}, token=il_owner["token"])
check("a limit of zero is a 422", status == 422, f"{status} {body}")

status, preview = call("GET", f"/invites/{code}")
check(
    "the preview needs no account",
    status == 200
    and preview == {
        "guild_name": "Open Door",
        "guild_description": "come in",
        "icon_url": None,
        "member_count": 2,
    },
    f"{status} {preview}",
)
status, body = call("GET", "/invites/not-a-real-code")
check("an unknown code is a 404", status == 404, f"{status} {body}")
status, body = call("POST", f"/invites/{code}/accept")
check("accepting needs an account (401)", status == 401, f"{status} {body}")

status, body = call("POST", f"/invites/{code}/accept", token=il_a["token"])
check(
    "anyone with the link can join",
    status == 200 and body == {"guild_id": ig, "already_member": False},
    f"{status} {body}",
)
_, il_channels = call("GET", "/channels/me", token=il_a["token"])
check(
    "joining by link joins the channels",
    len([c for c in il_channels or [] if c.get("guild_id") == ig]) == 2,
    str(il_channels),
)
_, il_rows = call("GET", f"/guilds/{ig}/members", token=il_owner["token"])
check(
    "they join as a plain member",
    {r["user_id"]: r["role"] for r in il_rows or []}.get(il_a["id"]) == "member",
    str(il_rows),
)

_, one_use = call("POST", f"/guilds/{ig}/invite-links", {"max_uses": 1}, token=il_owner["token"])
status, body = call("POST", f"/invites/{one_use['code']}/accept", token=il_a["token"])
check(
    "someone already in the guild is sent there without spending a use",
    status == 200 and (body or {}).get("already_member") is True,
    f"{status} {body}",
)
status, body = call("POST", f"/invites/{one_use['code']}/accept", token=il_b["token"])
check("a one-use link works once", status == 200, f"{status} {body}")
status, body = call("POST", f"/invites/{one_use['code']}/accept", token=il_c["token"])
check("and not twice", status == 404, f"{status} {body}")
status, body = call("GET", f"/invites/{one_use['code']}")
check("a used-up link has no preview", status == 404, f"{status} {body}")

_, expiring = call(
    "POST", f"/guilds/{ig}/invite-links", {"expires_in_hours": 1}, token=il_owner["token"]
)
check("an expiring link says when", bool(expiring.get("expires_at")), str(expiring))
psql(f"UPDATE guild_invite_links SET expires_at = now() - interval '1 minute' WHERE code = '{expiring['code']}'")
status, body = call("POST", f"/invites/{expiring['code']}/accept", token=il_c["token"])
check("an expired link is refused", status == 404, f"{status} {body}")

# A pending personal invite would otherwise be left to fail when accepted
_, personal = call("POST", f"/guilds/{ig}/invite", {"user_id": il_c["id"]}, token=il_owner["token"])
_, third = call("POST", f"/guilds/{ig}/invite-links", {}, token=il_member["token"])
status, body = call("POST", f"/invites/{third['code']}/accept", token=il_c["token"])
check("a plain member's link works", status == 200, f"{status} {body}")
_, pending = call("GET", "/guilds/invites/me", token=il_c["token"])
check("joining by link uses up a pending invite", pending == [], str(pending))

_, member_links = call("GET", f"/guilds/{ig}/invite-links", token=il_member["token"])
check(
    "a member lists only their own links",
    [l["code"] for l in member_links or []] == [third["code"]],
    str(member_links),
)
_, owner_links = call("GET", f"/guilds/{ig}/invite-links", token=il_owner["token"])
check(
    "an admin lists them all, and only live ones",
    code in [l["code"] for l in owner_links or []]
    and third["code"] in [l["code"] for l in owner_links or []]
    and one_use["code"] not in [l["code"] for l in owner_links or []]
    and expiring["code"] not in [l["code"] for l in owner_links or []],
    str(owner_links),
)
status, body = call("DELETE", f"/guilds/{ig}/invite-links/{code}", token=il_member["token"])
check("a member cannot revoke someone else's link (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{ig}/invite-links/{third['code']}", token=il_member["token"])
check("a member can revoke their own", status == 204, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{ig}/invite-links/{code}", token=il_owner["token"])
check("an admin can revoke anyone's", status == 204, f"{status} {body}")
status, body = call("GET", f"/invites/{code}")
check("a revoked link stops working", status == 404, f"{status} {body}")

_, parting = call("POST", f"/guilds/{ig}/invite-links", {}, token=il_a["token"])
status, _ = call("DELETE", f"/guilds/{ig}/members/{il_a['id']}", token=il_owner["token"])
status, body = call("POST", f"/invites/{parting['code']}/accept", token=il_a["token"])
check("removing someone ends the links they made", status == 404, f"{status} {body}")

print("== bans ==")
bn_owner, bn_mod, bn_admin, bn_member, bn_troll = (
    register("bn_owner"), register("bn_mod"), register("bn_admin"),
    register("bn_member"), register("bn_troll"),
)
_, bn_guild = call(
    "POST", "/guilds/", {"name": "Bans", "description": ""}, token=bn_owner["token"]
)
bg = bn_guild["id"]
for person in (bn_mod, bn_admin, bn_member, bn_troll):
    join(person, bg, bn_owner)
set_role(bn_owner, bn_mod, "moderator", bg)
set_role(bn_owner, bn_admin, "admin", bg)
_, bn_link = call("POST", f"/guilds/{bg}/invite-links", {}, token=bn_owner["token"])

status, body = call("POST", f"/guilds/{bg}/bans/{bn_troll['id']}", token=bn_member["token"])
check("a member cannot ban (403)", status == 403, f"{status} {body}")
status, body = call("POST", f"/guilds/{bg}/bans/{bn_admin['id']}", token=bn_mod["token"])
check("a moderator cannot ban an admin (403)", status == 403, f"{status} {body}")
status, body = call("POST", f"/guilds/{bg}/bans/{bn_owner['id']}", token=bn_admin["token"])
check("an admin cannot ban the owner (403)", status == 403, f"{status} {body}")
status, body = call("POST", f"/guilds/{bg}/bans/{bn_mod['id']}", token=bn_mod["token"])
check("nobody can ban themselves (403)", status == 403, f"{status} {body}")
status, body = call("POST", f"/guilds/{bg}/bans/{outsider['id']}", token=bn_owner["token"])
check("banning a non-member is a 404", status == 404, f"{status} {body}")

status, body = call("POST", f"/guilds/{bg}/bans/{bn_troll['id']}", token=bn_mod["token"])
check("a moderator can ban a member", status == 204, f"{status} {body}")
_, troll_guilds = call("GET", "/guilds/me", token=bn_troll["token"])
check("banning removes them", troll_guilds == [], str(troll_guilds))

status, body = call("POST", f"/invites/{bn_link['code']}/accept", token=bn_troll["token"])
check("a banned user cannot use a link (403)", status == 403, f"{status} {body}")
_, live = call("GET", f"/guilds/{bg}/invite-links", token=bn_owner["token"])
check("and the refusal does not spend a use", live[0]["uses"] == 0, str(live))
status, body = call(
    "POST", f"/guilds/{bg}/invite", {"user_id": bn_troll["id"]}, token=bn_owner["token"]
)
check("a banned user cannot be invited (403)", status == 403, f"{status} {body}")

status, body = call("GET", f"/guilds/{bg}/bans", token=bn_member["token"])
check("a member cannot read the ban list (403)", status == 403, f"{status} {body}")
status, bans = call("GET", f"/guilds/{bg}/bans", token=bn_mod["token"])
check(
    "a moderator can, with names",
    status == 200 and [b["username"] for b in bans or []] == [bn_troll["username"]],
    f"{status} {bans}",
)
status, body = call("DELETE", f"/guilds/{bg}/bans/{bn_troll['id']}", token=bn_member["token"])
check("a member cannot lift a ban (403)", status == 403, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{bg}/bans/{bn_troll['id']}", token=bn_mod["token"])
check("a ban can be lifted", status == 204, f"{status} {body}")
status, body = call("DELETE", f"/guilds/{bg}/bans/{bn_troll['id']}", token=bn_mod["token"])
check("lifting it twice is a 404", status == 404, f"{status} {body}")
_, troll_guilds = call("GET", "/guilds/me", token=bn_troll["token"])
check("lifting a ban does not bring them back", troll_guilds == [], str(troll_guilds))
status, body = call("POST", f"/invites/{bn_link['code']}/accept", token=bn_troll["token"])
check("but they can come back by invite", status == 200, f"{status} {body}")

print("== the demo survives a visitor with an owner's powers ==")


def demo_login():
    """Past the reset cooldown, so each login really resets."""
    subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "DEL", "demo:reset:cooldown"],
        capture_output=True,
    )
    status, body, _ = session_call("/demo/login")
    return (body or {}).get("access_token") if status == 200 else None


demo_token = demo_login()
if not demo_token:
    print("  SKIP  demo reset (DEMO_ENABLED is off)")
else:
    def demo_guild():
        _, guilds = call("GET", "/guilds/me", token=demo_token)
        return guilds[0] if guilds else {}

    def demo_snapshot():
        guild = demo_guild()
        _, rows = call("GET", f"/guilds/{guild.get('id')}/members", token=demo_token)
        _, channels = call("GET", "/channels/me", token=demo_token)
        return {
            "guild": (guild.get("name"), guild.get("description")),
            "roles": sorted(row["role"] for row in rows or []),
            "members": len(rows or []),
            "channels": sorted(
                c["name"] for c in channels or [] if c.get("guild_id") == guild.get("id")
            ),
        }

    clean = demo_snapshot()
    guild = demo_guild()
    _, rows = call("GET", f"/guilds/{guild['id']}/members", token=demo_token)
    cast = [row["user_id"] for row in rows if row["role"] == "member"]
    _, channels = call("GET", "/channels/me", token=demo_token)
    a_channel = [c for c in channels if c.get("guild_id") == guild["id"]][0]

    status, _ = call(
        "PATCH",
        f"/guilds/{guild['id']}/members/{cast[0]}",
        {"role": "admin"},
        token=demo_token,
    )
    check("a demo visitor can promote the cast", status == 200, f"got {status}")
    status, _ = call("DELETE", f"/guilds/{guild['id']}/members/{cast[1]}", token=demo_token)
    check("a demo visitor can remove the cast", status == 204, f"got {status}")
    status, _ = call("DELETE", f"/channels/{a_channel['id']}", token=demo_token)
    check("a demo visitor can delete a channel", status == 204, f"got {status}")
    status, _ = call(
        "PATCH",
        f"/guilds/{guild['id']}",
        {"description": "vandalised"},
        token=demo_token,
    )
    check("a demo visitor can edit the description", status == 200, f"got {status}")

    demo_token = demo_login()
    check(
        "roles, roster, channels and description come back",
        demo_snapshot() == clean,
        f"{demo_snapshot()} != {clean}",
    )

    guild = demo_guild()
    status, _ = call("PATCH", f"/guilds/{guild['id']}", {"name": "Mine now"}, token=demo_token)
    check("a demo visitor can rename the guild", status == 200, f"got {status}")
    demo_token = demo_login()
    check("a rename comes back", demo_snapshot() == clean, str(demo_snapshot()))

    guild = demo_guild()
    status, _ = call("DELETE", f"/guilds/{guild['id']}", token=demo_token)
    check("a demo visitor can delete the guild", status == 204, f"got {status}")
    demo_token = demo_login()
    check("a deleted guild comes back", demo_snapshot() == clean, str(demo_snapshot()))

    # Giving the guild away, and pulling a stranger in through a link
    guild = demo_guild()
    _, rows = call("GET", f"/guilds/{guild['id']}/members", token=demo_token)
    cast = [row["user_id"] for row in rows if row["role"] == "member"]
    status, demo_link = call("POST", f"/guilds/{guild['id']}/invite-links", {}, token=demo_token)
    check("a demo visitor can make an invite link", status == 201, f"got {status}")
    stranger = register("demo_stranger")
    status, _ = call("POST", f"/invites/{demo_link['code']}/accept", token=stranger["token"])
    check("a stranger can come in through it", status == 200, f"got {status}")
    status, _ = call(
        "POST", f"/guilds/{guild['id']}/transfer", {"user_id": cast[0]}, token=demo_token
    )
    check("a demo visitor can give the guild away", status == 200, f"got {status}")

    # A guild of someone else's that the visitor then joined
    outside = register("demo_outside")
    _, outside_guild = call(
        "POST", "/guilds/", {"name": "Outside", "description": ""}, token=outside["token"]
    )
    _, outside_link = call(
        "POST", f"/guilds/{outside_guild['id']}/invite-links", {}, token=outside["token"]
    )
    call("POST", f"/invites/{outside_link['code']}/accept", token=demo_token)

    demo_token = demo_login()
    check("a transferred guild comes back", demo_snapshot() == clean, str(demo_snapshot()))
    _, stranger_guilds = call("GET", "/guilds/me", token=stranger["token"])
    check("the stranger is out of it", stranger_guilds == [], str(stranger_guilds))
    status, _ = call("GET", f"/invites/{demo_link['code']}")
    check("the link is gone", status == 404, f"got {status}")
    _, demo_channels = call("GET", "/channels/me", token=demo_token)
    check(
        "a guild the visitor joined leaves no channels behind",
        not [c for c in demo_channels or [] if c.get("guild_id") == outside_guild["id"]],
        str(demo_channels),
    )

print("== a hostile websocket client ==")
# Fresh users: bob and alice share a DM that mallory has no part in
ws_alice, ws_bob, ws_mallory = register("wa_alice"), register("wa_bob"), register("wa_mal")
call(
    "POST",
    f"/friendship/friends/request?to_username={ws_bob['username']}",
    token=ws_alice["token"],
)
_, ws_requests = call("GET", "/friendship/friends/request/me", token=ws_bob["token"])
_, ws_accepted = call(
    "POST",
    f"/friendship/friends/request/{ws_requests[0]['id']}/accept",
    token=ws_bob["token"],
)
# The probe's duplicate-key attempt needs a row to collide with
psql(
    "INSERT INTO messages (id, sender_id, channel_id, content, created_at) VALUES "
    f"(gen_random_uuid(), '{ws_alice['id']}', '{ws_accepted['dm_channel_id']}', 'seed', now())"
)
run_probe(
    "ws_abuse_probe.py",
    {
        "alice": ws_alice,
        "bob": ws_bob,
        "mallory": ws_mallory,
        "channel_id": ws_accepted["dm_channel_id"],
        "max_message_length": 4000,
    },
    "websocket abuse probe",
)

print("== realtime events from rest mutations ==")
# Fresh users: this probe drives its own friend request and guild join
run_probe(
    "realtime_probe.py",
    {
        "alice": register("rt_alice"),
        "bob": register("rt_bob"),
        "carol": register("rt_carol"),
        "dave": register("rt_dave"),
    },
    "realtime probe",
)

print("== uploads ==")


def tiny_png(width=64, height=48) -> bytes:
    """A valid PNG from the stdlib alone: the host running this has no Pillow."""
    import struct
    import zlib

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    rows = b"".join(b"\x00" + b"\x20\x90\xd0" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def upload(method, path, data, token, filename="image.png", ctype="image/png"):
    """A multipart upload with one `file` field. Returns (status, parsed body)."""
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + path, data=body, method=method)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        payload = e.read().decode()
        return e.code, json.loads(payload) if payload.startswith("{") else payload


def fetch_media(url):
    """GET a /media URL through the edge. Returns (status, content type)."""
    try:
        with urllib.request.urlopen(BASE.removesuffix("/api") + url) as resp:
            return resp.status, resp.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        return e.code, None


# Found while adding avatars (2026-09-29): this route returned ORM User rows
# with no response model, so every friend's email and bcrypt hash went to the
# client, the same leak `GET /users/` had. This is the check that it stays shut.
status, friends = call("GET", "/friendship/friends/me", token=alice["token"], expect=200)
check(
    "friends list hides emails and password hashes",
    bool(friends)
    and all("email" not in f and "password_hash" not in f for f in friends),
    str(friends)[:200],
)

status, me = upload("PUT", "/users/me/avatar", tiny_png(), alice["token"])
avatar_url = (me or {}).get("avatar_url") if isinstance(me, dict) else None
check("avatar upload", status == 200 and bool(avatar_url), f"{status} {me}")
check(
    "avatar is stored as a key and served at /media",
    bool(avatar_url) and avatar_url.startswith("/media/avatars/") and avatar_url.endswith(".webp"),
    str(avatar_url),
)
check("avatar is served by the edge as webp", fetch_media(avatar_url or "/media/x") == (200, "image/webp"))

status, others_view = call("GET", f"/users/{alice['id']}/profile", token=bob["token"])
check("other people see the avatar", (others_view or {}).get("avatar_url") == avatar_url)

status, me = upload("PUT", "/users/me/avatar", tiny_png(32, 32), alice["token"])
check(
    "replacing an avatar deletes the old object",
    status == 200 and fetch_media(avatar_url or "/media/x")[0] == 404,
)
status, me = call("DELETE", "/users/me/avatar", token=alice["token"], expect=200)
check("clearing an avatar", (me or {}).get("avatar_url") is None, str(me))

status, refused = upload(
    "PUT", "/users/me/avatar", b"<html><script>alert(1)</script></html>", alice["token"]
)
check("a file that is not an image is refused (415)", status == 415, f"{status} {refused}")
status, refused = upload(
    "PUT", "/users/me/avatar", b"\x89PNG" + b"\x00" * (9 * 1024 * 1024), alice["token"]
)
check("an upload over 8 MB is refused (413)", status == 413, f"{status}")

status, icon = upload("PUT", f"/guilds/{shared_guild['id']}/icon", tiny_png(), bob["token"])
check("a non-admin cannot change the guild icon (403)", status == 403, f"{status} {icon}")
status, icon = upload("PUT", f"/guilds/{shared_guild['id']}/icon", tiny_png(), alice["token"])
check(
    "the admin can change the guild icon",
    status == 200 and str((icon or {}).get("icon_url", "")).startswith("/media/guild-icons/"),
    f"{status} {icon}",
)
check("guild responses never carry the raw key", "icon_key" not in (icon or {}))

status, attachment = upload("POST", "/uploads/attachments", tiny_png(3000, 20), alice["token"])
check(
    "attachment upload, scaled to 2048 on the long side",
    status == 201 and (attachment or {}).get("width") == 2048,
    f"{status} {attachment}",
)

if status == 201:
    run_probe(
        "attachment_probe.py",
        {
            "owner": alice,
            "other": bob,
            "channel_id": dm_channel_id,
            "attachment_id": attachment["id"],
        },
        "attachment probe",
    )

    _, dm_history = call("GET", f"/messages/{dm_channel_id}", token=alice["token"])
    with_image = [m for m in dm_history or [] if m.get("attachments")][-1]
    image_url = with_image["attachments"][0]["url"]
    check("the image is served before its message is deleted", fetch_media(image_url)[0] == 200)
    status, _ = call("DELETE", f"/messages/{with_image['id']}", token=alice["token"])
    check("a message with an image can be deleted", status == 204, f"got {status}")
    check("its image goes with it", fetch_media(image_url)[0] == 404)

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
