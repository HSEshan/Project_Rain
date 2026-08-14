# Project Rain

A self-hosted chat platform in the shape of Discord: direct messages, friends,
guilds with text channels, and a realtime event pipeline built to survive more
than one gateway instance. Voice is not implemented yet.

## Architecture

```
Browser
  HTTP  /api/*          -> Caddy -> rest_api:8000   -> Postgres
  WS    /ws?token=JWT   -> Caddy -> ws_gateway:8000 -> Postgres (message persist)
                                                    -> Redis stream_shard:{n}
event_consumer   reads the shards it holds a lease on
                 -> gRPC SendEvents -> ws_gateway:6000
                 -> websocket frames to that instance's clients
lease_manager    heartbeats + lease assignment (shard -> consumer)
```

| Service | Role |
|---------|------|
| `backend/rest_api` | FastAPI CRUD: auth, users, guilds, channels, friends, message history. Owns the database schema. |
| `backend/ws_gateway` | Websocket ingress, message persistence, publishes to Redis streams, gRPC server for inbound delivery. |
| `backend/event_consumer` | Reads leased stream shards, fans events out to the gateway holding each recipient. |
| `backend/lease_manager` | Assigns stream shards to live consumers. |
| `backend/libs` | Shared package: event schema/proto/codec, the Redis key helpers, structlog setup, and the SQLAlchemy models (`libs.db`). |
| `frontend` | React 19 + Vite 7 + TypeScript + Zustand + Tailwind. |

`rest_api` and `ws_gateway` import their ORM models from `libs.db` — one
definition, one engine configuration. `event_consumer` and `lease_manager`
install `libs` without the `db` extra and never touch Postgres.

## Running it

Docker Compose is the supported path. There is no standalone
`uvicorn` / `npm run dev` setup: the frontend talks to `/api` and `/ws` on the
same origin, and Caddy is what provides that origin.

```bash
python generate_env_files.py
```

Writes the gitignored `*.dev.env` files, including one `SECRET_KEY` shared by
`rest_api` and `ws_gateway` (they must agree or the websocket rejects every
token). It prompts on stdin; for a non-interactive run use
`python -c "import generate_env_files as g; g.main()"`.

```bash
cp Caddyfile.dev.example Caddyfile
```

`Caddyfile` itself is gitignored. Use `Caddyfile.dev.example` for local work
(`:8080`, frontend proxied to Vite on `:5173`); `Caddyfile.example` is the
production edge and will not work with `docker-compose.yml`.

```bash
docker compose up --build
```

The app is on <http://localhost:8080>. Eight containers should report healthy:
postgres, redis, rest_api, ws_gateway, event_consumer, lease_manager, frontend,
edge.

## Database schema

Alembic owns the schema. `rest_api` runs `upgrade head` during startup and is
the only service that migrates; `ws_gateway` waits for it to become healthy.

```bash
docker compose exec rest_api alembic revision --autogenerate -m "what changed"
docker compose exec rest_api alembic current
```

Autogenerate compares `libs.db` against the connected database, so a new model
must be imported in `libs/libs/db/models/__init__.py` or it will be invisible.

A database created before Alembic existed (by the old `create_all` path) is
detected at startup, stamped with the initial revision, and then upgraded
normally — no manual step.

## Tests

```bash
python backend/tests/e2e/smoke.py
```

End to end against a running stack, stdlib only (no host virtualenv needed —
it shells out to the `docker` CLI). Covers register → friend request → DM →
guild → invite → member removal, the websocket round trip, multiple sockets per
user, and realtime delivery of REST mutations. It writes real rows to the dev
database.

```bash
docker compose run --rm --no-deps rest_api python -m pytest tests -q
```

Unit tests for `rest_api`. These do not need a database.

## Deployment

`docker-compose-prod.yml` pulls images from GHCR (the `{GH_USERNAME}` /
`{GH_REPO_NAME}` placeholders still need filling in) and serves through Caddy on
80/443 using `Caddyfile.example`.
