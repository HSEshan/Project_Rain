"""Cross-file config check for a Project Rain deployment.

Several settings have to agree across services and nothing enforces that at
write time, because each service reads its own env file and can only see its own
half of the invariant. Every one of these has either bitten this project or is
one hand edit away from doing so:

- the shard count, where a mismatch silently drops events onto a stream nobody
  leases (see `backend/libs/libs/event/shards.py`)
- `SECRET_KEY`, where rest_api signs the JWT and ws_gateway verifies it
- the Postgres credentials, which three files repeat
- the LiveKit key pair, where rest_api mints tokens the SFU has to accept
- the Redis coordinates, which all four backend services must share

Stdlib only and no imports from the repo, so it runs on the VPS with nothing
installed:

    python check_config.py            # picks *.env if present, else *.dev.env
    python check_config.py --dev
    python check_config.py --prod

Exit code is 1 if anything failed, 0 otherwise. Values are compared, never
printed: the output is safe to paste into an issue.
"""

import os
import re
import sys

# Canonical name first. Kept in step with libs/libs/event/shards.py by hand,
# because this script deliberately imports nothing from the backend.
SHARD_COUNT_ENV = "NUM_SHARDS"
LEGACY_SHARD_COUNT_ENV = "NUM_STREAMS"
SHARD_COUNT_ENV_NAMES = (SHARD_COUNT_ENV, LEGACY_SHARD_COUNT_ENV)
DEFAULT_NUM_SHARDS = 16

# Services that need the shard count. event_consumer is not one of them: it
# discovers its shards from the leases hash.
SHARD_SERVICES = ("rest_api", "ws_gateway", "lease_manager")
REDIS_SERVICES = ("rest_api", "ws_gateway", "event_consumer", "lease_manager")

FAILURES = []
WARNINGS = []


def read_env(path):
    """Parse a docker `env_file`. Not a shell: no quoting, no expansion."""
    values = {}
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def fail(message):
    FAILURES.append(message)
    print(f"  FAIL  {message}")


def warn(message):
    WARNINGS.append(message)
    print(f"  WARN  {message}")


def ok(message):
    print(f"  PASS  {message}")


def shard_count(env):
    """(value, env var it came from) for one service, or (None, None)."""
    for name in SHARD_COUNT_ENV_NAMES:
        raw = env.get(name)
        if raw:
            return raw, name
    return None, None


def check_shards(envs):
    print("\nShard count")
    found = {}
    for service in SHARD_SERVICES:
        env = envs.get(service)
        if env is None:
            continue
        raw, source = shard_count(env)
        if raw is None:
            if service == "rest_api":
                fail(
                    f"{service} sets neither {SHARD_COUNT_ENV} nor "
                    f"{LEGACY_SHARD_COUNT_ENV}, so it falls back to "
                    f"{DEFAULT_NUM_SHARDS} and publishes onto shards nobody leases"
                )
            else:
                fail(f"{service} sets no {SHARD_COUNT_ENV}")
            continue
        try:
            found[service] = int(raw)
        except ValueError:
            fail(f"{service} {source} is not an integer")
            continue
        if source == LEGACY_SHARD_COUNT_ENV:
            warn(
                f"{service} still uses {LEGACY_SHARD_COUNT_ENV}; it is accepted "
                f"but deprecated, rename it to {SHARD_COUNT_ENV}"
            )

    if len(set(found.values())) > 1:
        fail(f"services disagree on the shard count: {found}")
    elif len(found) == len(SHARD_SERVICES):
        ok(f"all of {', '.join(SHARD_SERVICES)} agree on {SHARD_COUNT_ENV}")

    consumer = envs.get("event_consumer")
    if consumer is not None and shard_count(consumer)[0] is not None:
        warn(
            "event_consumer carries a shard count that nothing reads; it leases "
            "its shards. Remove the line so it cannot look authoritative"
        )


def check_same(envs, services, keys, label):
    print(f"\n{label}")
    present = [s for s in services if envs.get(s) is not None]
    if len(present) < 2:
        return
    for key in keys:
        values = {s: envs[s].get(key) for s in present}
        missing = [s for s, v in values.items() if v is None]
        if missing:
            # A missing key is either a built-in default (fine until the rest of
            # the deployment moves off it) or a service that will refuse to
            # start. Both are visible; silent divergence is what this checks for.
            warn(f"{key} is not set in {', '.join(missing)}, relying on defaults")
            values = {s: v for s, v in values.items() if v is not None}
            if len(values) < 2:
                continue
        names = ", ".join(values)
        if len(set(values.values())) > 1:
            fail(f"{key} differs across {names}")
        else:
            ok(f"{key} matches across {names}")


def check_livekit(envs, livekit_env_path, livekit_yaml_path):
    print("\nLiveKit")
    rest = envs.get("rest_api")
    if rest is None:
        return

    key = rest.get("LIVEKIT_API_KEY")
    secret = rest.get("LIVEKIT_API_SECRET")
    if not secret:
        warn(
            "rest_api has no LIVEKIT_API_SECRET; the voice endpoints return 503 "
            "rather than minting tokens the SFU would reject"
        )
        return

    livekit = read_env(livekit_env_path)
    if livekit is None:
        fail(f"{livekit_env_path} is missing, so the SFU has no keys")
        return

    # LIVEKIT_KEYS is `name: secret`, one pair per line in the general case.
    pairs = {}
    for line in livekit.get("LIVEKIT_KEYS", "").split(","):
        name, _, value = line.partition(":")
        if value:
            pairs[name.strip()] = value.strip()

    if key not in pairs:
        fail(f"LIVEKIT_API_KEY is not one of the keys the SFU was started with")
    elif pairs[key] != secret:
        fail("LIVEKIT_API_SECRET does not match the SFU's secret for that key")
    else:
        ok("rest_api and the SFU share the same API key pair")

    if not os.path.exists(livekit_yaml_path):
        warn(f"{livekit_yaml_path} not found, skipping the webhook check")
        return

    with open(livekit_yaml_path, encoding="utf-8") as f:
        yaml = f.read()
    webhook = re.search(r"webhook:.*?api_key:\s*(\S+)", yaml, re.DOTALL)
    if webhook is None:
        warn(
            f"{livekit_yaml_path} sets no webhook.api_key; voice rosters go "
            "stale because LiveKit is the only writer of them"
        )
    elif webhook.group(1).strip("\"'") != key:
        fail(f"{livekit_yaml_path} webhook.api_key is not LIVEKIT_API_KEY")
    else:
        ok("the SFU signs webhooks with the key rest_api verifies")


def main(argv):
    if "--dev" in argv:
        suffix = ".dev.env"
    elif "--prod" in argv:
        suffix = ".env"
    elif os.path.exists("rest_api.env"):
        suffix = ".env"
    else:
        suffix = ".dev.env"

    print(f"Checking *{suffix} in {os.getcwd()}")

    envs = {}
    for service in ("rest_api", "ws_gateway", "event_consumer", "lease_manager", "postgres"):
        path = service + suffix
        env = read_env(path)
        if env is None:
            fail(f"{path} is missing")
        else:
            envs[service] = env

    check_shards(envs)
    check_same(envs, ("rest_api", "ws_gateway"), ("SECRET_KEY", "ALGORITHM"), "JWT")
    check_same(
        envs,
        ("rest_api", "ws_gateway", "postgres"),
        ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"),
        "Postgres",
    )
    check_same(
        envs,
        REDIS_SERVICES,
        ("REDIS_HOST", "REDIS_PORT", "REDIS_DB"),
        "Redis",
    )
    check_livekit(
        envs,
        "livekit" + suffix,
        "livekit.dev.yaml" if suffix == ".dev.env" else "livekit.yaml",
    )

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failed, {len(WARNINGS)} warnings")
        return 1
    print(f"config consistent ({len(WARNINGS)} warnings)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
