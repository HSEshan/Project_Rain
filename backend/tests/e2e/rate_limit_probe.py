"""Rate limits against a live stack, with the limits switched on.

The compose stack runs with them off, because `smoke.py` registers dozens of
accounts from one address. This is the other half, and it has to go through the
real edge: which address a limit is keyed on is decided by Caddy, not by anything
a unit test can see.

    RATE_LIMIT_ENABLED=true docker compose up -d --wait rest_api ws_gateway
    python backend/tests/e2e/rate_limit_probe.py
    docker compose up -d --wait rest_api ws_gateway

Stdlib only, like `smoke.py`.
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
FAILURES = []


def check(name, ok, detail=""):
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


def send(method, path, body=None, token=None, headers=None, form=None):
    """Returns (status, parsed body, response headers)."""
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
    elif body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header(
        "Content-Type",
        "application/x-www-form-urlencoded" if form is not None else "application/json",
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None, resp.headers
    except urllib.error.HTTPError as err:
        raw = err.read().decode()
        try:
            return err.code, json.loads(raw), err.headers
        except ValueError:
            return err.code, raw, err.headers


def clear_counters():
    subprocess.run(
        [
            "docker", "compose", "exec", "-T", "redis", "sh", "-c",
            "redis-cli --scan --pattern 'ratelimit:*' | xargs -r redis-cli del",
        ],
        capture_output=True,
    )


def register():
    name = f"rl_{uuid.uuid4().hex[:8]}"
    creds = {"username": name, "email": f"{name}@example.com", "password": "Passw0rd!23"}
    status, created, _ = send("POST", "/auth/register", creds)
    if status != 201:
        raise SystemExit(f"register failed: {status} {created}")
    status, session, _ = send(
        "POST",
        "/auth/login",
        form={"username": creds["email"], "password": creds["password"]},
    )
    if status != 200:
        raise SystemExit(f"login failed: {status} {session}")
    return {"id": created["id"], "username": name, "token": session["access_token"]}


print("== the limits are on ==")
clear_counters()
statuses = [
    send("POST", "/auth/login", form={"username": "x@example.com", "password": "wrong"})[0]
    for _ in range(11)
]
if statuses[-1] != 429:
    raise SystemExit(
        f"limits look off, got {statuses}. Start the stack with "
        "RATE_LIMIT_ENABLED=true (see this file's docstring)."
    )
check("ten wrong passwords are answered 401", statuses[:10] == [401] * 10, str(statuses))
check("the eleventh is 429", statuses[10] == 429, str(statuses))

print("== a refusal a client can act on ==")
status, body, headers = send(
    "POST", "/auth/login", form={"username": "x@example.com", "password": "wrong"}
)
check("it carries Retry-After", int(headers.get("Retry-After") or 0) >= 1, str(headers))
check(
    "its detail is a sentence with a wait in it",
    isinstance((body or {}).get("detail"), str) and "Try again in" in body["detail"],
    str(body),
)

print("== keyed on the account, across addresses ==")
status, _, _ = send(
    "POST",
    "/auth/login",
    form={"username": "X@Example.com ", "password": "wrong"},
    headers={"X-Real-IP": "198.51.100.1"},
)
check("case and spacing do not make a new account", status == 429, f"got {status}")
status, _, _ = send(
    "POST", "/auth/login", form={"username": "y@example.com", "password": "wrong"}
)
check("another account is unaffected", status == 401, f"got {status}")

print("== the address cannot be chosen by the client ==")
clear_counters()
statuses = [
    send(
        "POST",
        "/auth/register",
        {"username": "", "email": "", "password": ""},
        headers={
            "X-Forwarded-For": f"10.0.0.{index}",
            "X-Real-IP": f"10.0.0.{index}",
            "Forwarded": f"for=10.0.0.{index}",
        },
    )[0]
    for index in range(11)
]
check(
    "rotating forwarding headers does not reset the limit",
    statuses == [422] * 10 + [429],
    str(statuses),
)

print("== a limited refresh must not end the session ==")
clear_counters()
for _ in range(60):
    send("POST", "/auth/refresh")
status, _, headers = send("POST", "/auth/refresh")
check("refresh is limited", status == 429, f"got {status}")
check(
    "and it does not clear the cookies",
    not headers.get_all("Set-Cookie"),
    str(headers.get_all("Set-Cookie")),
)

print("== a limit per account ==")
clear_counters()
alice, bob = register(), register()
statuses = [
    send("PATCH", "/users/me", {"bio": str(index)}, token=alice["token"])[0]
    for index in range(21)
]
check(
    "profile writes are limited",
    statuses == [200] * 20 + [429],
    str(statuses),
)
status, _, _ = send("PATCH", "/users/me", {"bio": "mine"}, token=bob["token"])
check("another account on one address is not", status == 200, f"got {status}")

print("== guessing at invite codes ==")
clear_counters()
statuses = [send("GET", f"/invites/guess-{index}")[0] for index in range(61)]
check("previews are limited", statuses == [404] * 60 + [429], str(statuses[-3:]))

print("== the websocket ==")
send(
    "POST",
    f"/friendship/friends/request?to_username={bob['username']}",
    token=alice["token"],
)
_, requests_, _ = send("GET", "/friendship/friends/request/me", token=bob["token"])
_, accepted, _ = send(
    "POST", f"/friendship/friends/request/{requests_[0]['id']}/accept", token=bob["token"]
)
probe = pathlib.Path(__file__).with_name("ws_rate_limit_probe.py")
result = subprocess.run(
    [
        "docker", "compose", "exec", "-T", "ws_gateway", "python", "-",
        json.dumps(
            {"sender": alice, "other": bob, "channel_id": accepted["dm_channel_id"]}
        ),
    ],
    stdin=probe.open("rb"),
    capture_output=True,
    text=True,
)
print(result.stdout.rstrip() or "  FAIL  the websocket probe produced no output")
if result.returncode != 0:
    FAILURES.append(f"websocket probe: {result.stderr[-600:]}")

clear_counters()
print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S):")
    for failure in FAILURES:
        print(" -", failure)
    sys.exit(1)
print("ALL CHECKS PASSED")
