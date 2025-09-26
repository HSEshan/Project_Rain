import os
import subprocess
import sys


def main():
    postgres_password = os.urandom(32).hex()
    secret_key = os.urandom(32).hex()
    superuser_password = os.urandom(32).hex()
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
NUM_SHARDS=16
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
NUM_STREAMS=16
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
NUM_STREAMS=16
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


if __name__ == "__main__":
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
