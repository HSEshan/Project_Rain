# Project Rain

**Live demo:** https://voice.eshanhs.dev

A self-hosted chat platform in the shape of Discord: direct messages, group
DMs, friends, profile cards, guilds with text and voice channels, calls inside a
DM, and a realtime event pipeline built to survive more than one gateway
instance.

Voice runs on a self-hosted LiveKit SFU and has been tested between two people
in different states for a two-hour session. A call in a DM uses the same rooms:
the room id is the channel id, so the membership that lets you into a guild
voice channel is the same membership that lets you call a friend.

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

`rest_api` and `ws_gateway` import their ORM models from `libs.db` - one
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
gatekeeper - it mints a join token only for a member of a `guild_voice`
channel - and the LiveKit room name is the channel id.

To try it with two people, invite someone with "+ Invite people" in a guild's
channel bar; the invitation appears for them on `/guild`. Two browser windows
on one machine need **separate sessions** (a second browser, or a private
window) - the login token is a cookie, and LiveKit allows one connection per
identity per room, so two windows signed in as the same user would evict each
other.

Signalling is proxied at `/livekit` so the browser needs no second host, but
**media is UDP straight to port 7882** and cannot go through Caddy. In
production that port has to be open, or voice connects and then nobody can hear
anyone. `livekit.dev.yaml` is the development config; copy
`livekit.example.yaml` to `livekit.yaml` for production, where ICE has to
advertise a real external address rather than the dev config's loopback.

Who is in a voice channel comes from LiveKit, through signed webhooks to
`POST /voice/webhook` - the browser never reports its own presence, because one
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
normally - no manual step.

## Tests

```bash
python backend/tests/e2e/smoke.py
```

End to end against a running stack, stdlib only (no host virtualenv needed -
it shells out to the `docker` CLI). Covers register → friend request → DM →
guild → invite → member removal, the websocket round trip, multiple sockets per
user, realtime delivery of REST mutations, and voice - including having LiveKit
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

```bash
python -m unittest discover -s backend/tests/unit
```

Tests for the `check_config.py` ops script. Stdlib only, so this one needs
nothing installed at all.

```bash
python -m unittest discover -s backend/libs/tests
```

Shard count resolution and the startup agreement check. Needs `libs` importable
(`pip install ./backend/libs`), or run it in a service image.

CI runs all of the above plus the frontend lint and build on every push and pull
request: `.github/workflows/ci.yml`.

## Configuration

Env files are generated, never committed:

```bash
python generate_env_files.py
```

Several settings have to agree across files that no single service can see both
halves of. `check_config.py` compares them:

```bash
python check_config.py
```

It checks the shard count (`NUM_SHARDS` in rest_api, ws_gateway and
lease_manager), the JWT `SECRET_KEY` that rest_api signs with and ws_gateway
verifies, the Postgres credentials, the LiveKit API key pair and webhook key,
and the Redis coordinates. Values are compared, never printed, so the output is
safe to paste into an issue. It picks `*.env` when they exist and `*.dev.env`
otherwise; `--dev` and `--prod` force the choice. Stdlib only, so it runs on the
VPS with nothing installed.

`NUM_STREAMS` is the old name for `NUM_SHARDS`. Both still work and the new one
wins, so an env file written before the rename keeps running; the alias will be
dropped in a later release.

### Sessions

Signing in returns two credentials. The **access token** is a JWT in a cookie
the page can read, because the websocket is opened as `/ws?token=...`; it lasts
`ACCESS_TOKEN_MINUTES` (60). The **refresh token** is opaque, lives in an
`httpOnly` cookie scoped to `/api/auth`, and is exchanged at `POST /auth/refresh`
for a new access token. Each exchange rotates it: the presented token is
revoked and its successor is issued into the same family, so a token presented
twice means two parties hold one session and the whole family is revoked.

| Setting | Default | What it means |
|---------|---------|----------------|
| `ACCESS_TOKEN_MINUTES` | 60 | How long a copied access token keeps working. It cannot be revoked, so this is the only limit on it |
| `REFRESH_TOKEN_DAYS` | 30 | How long a sign-in lasts in total. A rotated token inherits its predecessor's expiry, so this is an absolute lifetime, not an idle timeout |
| `REFRESH_REUSE_GRACE_SECONDS` | 15 | A token replayed this soon after being spent is treated as a duplicate request (two tabs, a retry) rather than as theft |

A third cookie, `rain_session`, is readable and holds nothing but `1`. It tells
the client that a session exists at all, which it cannot otherwise know because
the refresh cookie is `httpOnly`; without it every anonymous visit to the
landing page would send a refresh request and be answered 401.

The refresh cookie is `Secure` in every environment but `development`, which is
served over plain http. `POST /auth/logout` revokes the family server-side.

## Backups

```bash
./backup.sh          # nightly via cron on the VPS; --dev for the dev stack
./restore.sh <dump>  # stops the writers, restores, restarts, prints the counts
```

`backup.sh` dumps Postgres, gzips it, refuses to keep a dump that is not valid
gzip or contains no tables, and prunes to the newest 30. `restore.sh` asks you
to type the database name rather than `y`. Both are documented in `DEPLOY.md`
R10a, including the cron line and the `OFFSITE_CMD` hook for copying a dump off
the box, which is the part a same-machine backup does not cover.

Run the restore against the dev stack before you need it in anger. A backup
nobody has restored is a hope.

## Deployment

`docker-compose-prod.yml` builds the images on the target host and runs Caddy as
an internal router on `127.0.0.1:8081` (`Caddyfile.example`), with host Nginx
terminating TLS in front of it (`nginx.conf.example`). Generate the production
env files with `python generate_env_files.py --prod`.

LiveKit media needs **7882/udp** (and 7881/tcp as a fallback) open on both the
host firewall and the provider's security group - no reverse proxy can carry it,
and a closed port fails as "voice connects, then nobody can hear anyone".
