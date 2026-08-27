import os
import subprocess
import sys


def main(prod: bool = False):
    """Write the gitignored env files.

    Dev writes `*.dev.env` for docker-compose.yml; `--prod` writes the `*.env`
    names docker-compose-prod.yml expects, with production logging and no docs
    endpoint. The two sets are deliberately separate files so deploying cannot
    quietly reuse a development secret.
    """
    if prod:
        return main_prod()

    postgres_password = os.urandom(32).hex()
    secret_key = os.urandom(32).hex()
    superuser_password = os.urandom(32).hex()
    # rest_api mints LiveKit join tokens, so it and the SFU must share this
    livekit_api_key = "devkey"
    livekit_api_secret = os.urandom(32).hex()
    with open("rest_api.dev.env", "w") as f:
        f.write(
            f"""
ENVIRONMENT=development
LOG_LEVEL=DEBUG
LOG_FORMAT=pretty
POSTGRES_USER=superuser
POSTGRES_PASSWORD={postgres_password.strip()}
POSTGRES_DB=devdb
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
SECRET_KEY={secret_key.strip()}
ALGORITHM=HS256
BCRYPT_ROUNDS=10
SUPERUSER_EMAIL=superuser@admin.com
SUPERUSER_PASSWORD={superuser_password.strip()}
DOCS=true
DEMO_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
NUM_SHARDS=2
LIVEKIT_API_KEY={livekit_api_key}
LIVEKIT_API_SECRET={livekit_api_secret.strip()}
LIVEKIT_PUBLIC_PATH=/livekit
            """.strip()
        )
    with open("livekit.dev.env", "w") as f:
        f.write(
            f"""
LIVEKIT_KEYS={livekit_api_key}: {livekit_api_secret.strip()}
            """.strip()
        )
    with open("ws_gateway.dev.env", "w") as f:
        f.write(
            f"""
ENVIRONMENT=development
LOG_LEVEL=DEBUG
LOG_FORMAT=pretty
POSTGRES_USER=superuser
POSTGRES_PASSWORD={postgres_password.strip()}
POSTGRES_DB=devdb
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
SECRET_KEY={secret_key.strip()}
ALGORITHM=HS256
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
NUM_SHARDS=2
BATCH_SIZE=100
BATCH_INTERVAL_MS=1
DEFAULT_TTL_SECONDS=300
GRPC_HOST=ws_gateway
GRPC_PORT=6000
# Address other services reach THIS gateway on. Only needed with more
# than one replica, where the service name above would load-balance and
# events would land on a gateway that does not hold the socket. On
# Kubernetes set it from status.podIP via the downward API.
GRPC_ADVERTISE_HOST=
            """.strip()
        )
    with open("event_consumer.dev.env", "w") as f:
        f.write(
            f"""
ENVIRONMENT=development
LOG_LEVEL=DEBUG
LOG_FORMAT=pretty
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
# No shard count here on purpose: event_consumer discovers its shards from the
# leases hash, so it never needs one. NUM_SHARDS belongs to rest_api,
# ws_gateway and lease_manager, and all three must carry the same value.
REDIS_XREAD_COUNT=100
REDIS_XREAD_BLOCK=25
CONSUMER_GROUP=grpc_group
HEARTBEAT_TTL=15
GRPC_TIMEOUT=5
MAX_GRPC_CONNECTIONS=100

            """.strip()
        )
    with open("lease_manager.dev.env", "w") as f:
        f.write(
            f"""
ENVIRONMENT=development
LOG_LEVEL=DEBUG
LOG_FORMAT=pretty
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
NUM_SHARDS=2
            """.strip()
        )
    write_frontend_env()
    with open("postgres.dev.env", "w") as f:
        f.write(
            f"""
ENVIRONMENT=development
LOG_LEVEL=debug
LOG_FORMAT=pretty
POSTGRES_USER=superuser
POSTGRES_PASSWORD={postgres_password.strip()}
POSTGRES_DB=devdb
            """.strip()
        )


DEFAULT_GIT_REPO_URL = "https://github.com/HSEshan/Project_Rain"


def write_frontend_env(path: str = "frontend/.env") -> None:
    """Write the Vite env for the landing page's outbound links.

    One file for dev and prod: the dev server reads it live, and
    Dockerfile.prod copies it in before `npm run build`, which is when Vite
    inlines `import.meta.env.VITE_*` into the bundle. Only VITE_-prefixed keys
    reach the browser, and everything here is public anyway.

    An existing file is left alone, so a customised repo URL survives
    regenerating the backend secrets.
    """
    if os.path.exists(path):
        print(f"kept existing {path}")
        return

    repo_url = os.getenv("GIT_REPO_URL", DEFAULT_GIT_REPO_URL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(
            f"""# Public links shown on the landing page. Safe to expose: Vite inlines
# every VITE_* value into the client bundle.
VITE_GIT_REPO_URL={repo_url}
# Swagger UI. rest_api runs with root_path=/api, so its /docs is reachable at
# /api/docs through Caddy. Requires DOCS=true in the rest_api env.
VITE_API_DOCS_PATH=/api/docs
"""
        )
    print(f"wrote {path}")


def main_prod():
    """Env files for docker-compose-prod.yml.

    Same shape as dev with four differences: production logging (json), the
    OpenAPI docs endpoint off, a real LiveKit API key name instead of `devkey`,
    and `postgres.env` naming a `raindb` rather than `devdb`.
    """
    postgres_password = os.urandom(32).hex()
    secret_key = os.urandom(32).hex()
    superuser_password = os.urandom(32).hex()
    livekit_api_key = "rainkey"
    livekit_api_secret = os.urandom(32).hex()

    postgres_block = f"""POSTGRES_USER=rain
POSTGRES_PASSWORD={postgres_password}
POSTGRES_DB=raindb
POSTGRES_HOST=postgres
POSTGRES_PORT=5432"""

    common = """ENVIRONMENT=production
LOG_LEVEL=INFO
LOG_FORMAT=json"""

    files = {
        "rest_api.env": f"""{common}
{postgres_block}
SECRET_KEY={secret_key}
ALGORITHM=HS256
BCRYPT_ROUNDS=12
SUPERUSER_EMAIL=superuser@admin.com
SUPERUSER_PASSWORD={superuser_password}
DOCS=true
DEMO_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
NUM_SHARDS=2
LIVEKIT_API_KEY={livekit_api_key}
LIVEKIT_API_SECRET={livekit_api_secret}
LIVEKIT_PUBLIC_PATH=/livekit""",
        # The SFU and rest_api must agree on this pair — rest_api mints the
        # join tokens and LiveKit verifies them.
        "livekit.env": f"LIVEKIT_KEYS={livekit_api_key}: {livekit_api_secret}",
        "ws_gateway.env": f"""{common}
{postgres_block}
SECRET_KEY={secret_key}
ALGORITHM=HS256
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
NUM_SHARDS=2
BATCH_SIZE=100
BATCH_INTERVAL_MS=1
DEFAULT_TTL_SECONDS=300
GRPC_HOST=ws_gateway
GRPC_PORT=6000
# Address other services reach THIS gateway on. Only needed with more
# than one replica, where the service name above would load-balance and
# events would land on a gateway that does not hold the socket. On
# Kubernetes set it from status.podIP via the downward API.
GRPC_ADVERTISE_HOST=""",
        "event_consumer.env": f"""{common}
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
# No shard count here on purpose: event_consumer discovers its shards from the
# leases hash, so it never needs one. NUM_SHARDS belongs to rest_api,
# ws_gateway and lease_manager, and all three must carry the same value.
REDIS_XREAD_COUNT=100
REDIS_XREAD_BLOCK=25
CONSUMER_GROUP=grpc_group
HEARTBEAT_TTL=15
GRPC_TIMEOUT=5
MAX_GRPC_CONNECTIONS=100""",
        "lease_manager.env": f"""{common}
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
NUM_SHARDS=2""",
        "postgres.env": f"""POSTGRES_USER=rain
POSTGRES_PASSWORD={postgres_password}
POSTGRES_DB=raindb""",
    }

    for name, body in files.items():
        with open(name, "w") as f:
            f.write(body.strip() + "\n")
        print(f"wrote {name}")

    write_frontend_env()

    print(
        "\nNUM_SHARDS must stay equal across rest_api, ws_gateway and "
        "lease_manager - all three are 2 above. Run `python check_config.py` "
        "after any hand edit.\n"
        "Next: copy livekit.example.yaml to livekit.yaml and set its "
        f"`webhook.api_key` to {livekit_api_key}."
    )


if __name__ == "__main__":
    prod = "--prod" in sys.argv
    if prod:
        confirmation = input(
            "Generate PRODUCTION env files? This overwrites *.env and the new "
            "Postgres password will not match an existing volume (y/n): "
        )
        if confirmation != "y":
            print("Exiting...")
            sys.exit(0)
        main(prod=True)
        sys.exit(0)

    confirmation = input(
        "Are you sure you want to generate new env files? This will overwrite existing files (you must wipe Postgres volume after this) (y/n): "
    )
    if confirmation != "y":
        print("Exiting...")
        sys.exit(0)
    main()
    confirmation = input("Delete Postgres volume? (will docker compose down) (y/n): ")
    if confirmation == "y":
        subprocess.run(["docker", "compose", "down"])

        subprocess.run(["docker", "volume", "rm", "project_rain_postgres_data"])
        print("Postgres volume deleted")
    else:
        print("Exiting...")
        sys.exit(0)
