# Project Rain

A self-hosted chat platform in the shape of Discord: direct messages, friends,
guilds with text and voice channels, and a realtime event pipeline built to
survive more than one gateway instance.

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

  WS    /livekit         -> Caddy -> livekit:7880   (voice signalling)
  UDP   :7882            -> livekit                 (voice media, direct)
```

Voice audio deliberately bypasses everything above it: the browser talks WebRTC
to the SFU, and only presence ("X joined voice") travels the event pipeline.

| Service | Role |
|---------|------|
| `backend/rest_api` | FastAPI CRUD: auth, users, guilds, channels, friends, message history. Owns the database schema. |
| `backend/ws_gateway` | Websocket ingress, message persistence, publishes to Redis streams, gRPC server for inbound delivery. |
| `backend/event_consumer` | Reads leased stream shards, fans events out to the gateway holding each recipient. |
| `backend/lease_manager` | Assigns stream shards to live consumers. |
| `backend/libs` | Shared package: event schema/proto/codec, the Redis key helpers, structlog setup, and the SQLAlchemy models (`libs.db`). |
| `livekit` | Self-hosted SFU carrying voice channel audio. |
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
token) and one LiveKit key/secret shared by `rest_api` and the SFU (`rest_api`
mints the join tokens). It prompts on stdin; for a non-interactive run use
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

The app is on <http://localhost:8080>. Nine containers should come up:
postgres, redis, rest_api, ws_gateway, event_consumer, lease_manager, livekit,
frontend, edge.

## Voice

Guild voice channels connect to a self-hosted LiveKit SFU. `rest_api` is the
gatekeeper — it mints a join token only for a member of a `guild_voice`
channel — and the LiveKit room name is the channel id.

To try it with two people, invite someone with "+ Invite people" in a guild's
channel bar; the invitation appears for them on `/guild`. Two browser windows
on one machine need **separate sessions** (a second browser, or a private
window) — the login token is a cookie, and LiveKit allows one connection per
identity per room, so two windows signed in as the same user would evict each
other.

Signalling is proxied at `/livekit` so the browser needs no second host, but
**media is UDP straight to port 7882** and cannot go through Caddy. In
production that port has to be open, or voice connects and then nobody can hear
anyone. `livekit.dev.yaml` is the development config; copy
`livekit.example.yaml` to `livekit.yaml` for production, where ICE has to
advertise a real external address rather than the dev config's loopback.

Who is in a voice channel comes from LiveKit, through signed webhooks to
`POST /voice/webhook` — the browser never reports its own presence, because one
that refreshes or crashes would never get to say it left. `webhook.urls` must
therefore be set in the LiveKit config, or the participant lists stay empty.

Keep `livekit-client` in `frontend/package.json` in step with the server image
in the compose files: a client newer than the server wastes a failed request on
every join.

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
user, realtime delivery of REST mutations, and voice — including having LiveKit
itself validate a minted token and accept a signalling connection. It writes
real rows to the dev database.

```bash
docker compose run --rm --no-deps rest_api python -m pytest tests -q
```

Unit tests for `rest_api`. These do not need a database.

```bash
docker compose run --rm --no-deps event_consumer python -m unittest discover -s tests
```

Unit tests for the consumer's gRPC endpoint cache. Stdlib `unittest`, so that
image needs no test dependency.

## Deployment

`docker-compose-prod.yml` builds the images on the target host and runs Caddy as
an internal router on `127.0.0.1:8081` (`Caddyfile.example`), with host Nginx
terminating TLS in front of it (`nginx.conf.example`). Generate the production
env files with `python generate_env_files.py --prod`.

LiveKit media needs **7882/udp** (and 7881/tcp as a fallback) open on both the
host firewall and the provider's security group — no reverse proxy can carry it,
and a closed port fails as "voice connects, then nobody can hear anyone".
