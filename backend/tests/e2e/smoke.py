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
