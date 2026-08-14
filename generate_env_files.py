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
NUM_STREAMS=2
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
NUM_STREAMS=2
            """.strip()
        )
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
DOCS=false
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
GRPC_PORT=6000""",
        "event_consumer.env": f"""{common}
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
NUM_STREAMS=2
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
NUM_STREAMS=2""",
        "postgres.env": f"""POSTGRES_USER=rain
POSTGRES_PASSWORD={postgres_password}
POSTGRES_DB=raindb""",
    }

    for name, body in files.items():
        with open(name, "w") as f:
            f.write(body.strip() + "\n")
        print(f"wrote {name}")

    print(
        "\nNUM_SHARDS (ws_gateway) and NUM_STREAMS (consumer, lease manager) "
        "must stay equal - both are 2 above.\n"
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
