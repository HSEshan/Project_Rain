# Project Rain on AWS

A complete deployment of Project Rain on AWS, built to be stood up, learned
from, and torn down: **EC2** runs the stack, **S3** holds the frontend,
uploaded images and releases, **CloudFront** is the single public entry point,
**CloudWatch** gets every log line and pages you when something breaks, and
**RDS** can optionally replace the Postgres container.

Production stays on the VPS (tasks.md, Phase 21). Nothing here migrates data
from it, and nothing on the VPS depends on this.

- [Architecture](#architecture)
- [What it costs](#what-it-costs)
- [Prerequisites](#prerequisites)
- [Stand it up](#stand-it-up)
- [Day to day](#day-to-day)
- [Tear it down](#tear-it-down)
- [How each piece works, and why](#how-each-piece-works-and-why)
- [Gotchas this stack already handles](#gotchas-this-stack-already-handles)
- [Troubleshooting](#troubleshooting)
- [Beyond the proof of concept](#beyond-the-proof-of-concept)

---

## Architecture

```
                         https://<id>.cloudfront.net   (or your domain)
                                       |
                               +---------------+
      browser ---- HTTPS ----> |  CloudFront   |  one hostname, routed by path
                               +---------------+
                   /*   |          /media/*   |           /api/*  /ws*  /livekit/*
          (SPA rewrite) |                     |           + X-Origin-Verify header
                        v                     v                     |  HTTP :80
              +-----------------+   +-----------------+             |  (CloudFront
              | S3: frontend    |   | S3: media       |             |   ranges only)
              | (private, OAC)  |   | (private, OAC)  |             v
              +-----------------+   +-----------------+   +----------------------------+
                                            ^             | EC2 t4g.small (AL2023)     |
                                            | PutObject   |  docker compose:           |
                                            +-------------|   edge (Caddy :80)         |
                                              (instance   |   rest_api  ws_gateway     |
                                               role)      |   event_consumer  lease_mgr|
                                                          |   redis  livekit           |
     browser ==== WebRTC UDP 7882 (voice) ==============> |   postgres (or RDS below)  |
                                                          +----------------------------+
                                                             |  awslogs      |  5432 (optional)
                                                             v               v
                                                  +------------------+  +-------------------+
                                                  | CloudWatch Logs  |  | RDS Postgres 16   |
                                                  | metric filter    |  | private subnets   |
                                                  | alarms -> SNS    |  +-------------------+
                                                  +------------------+
```

The same containers as the VPS, from the same `docker-compose-prod.yml`, with
three overrides (`aws/docker-compose.aws.yml`): logs go to CloudWatch, there
is no frontend container, and Caddy listens on :80 for CloudFront only.

| Directory | What is in it |
|---|---|
| `terraform/` | Every AWS resource. One `terraform destroy` removes all of it |
| `scripts/` | What you run from your machine: up, deploy, stop, start, status, logs, shell, test-alarm, teardown |
| `instance/` | What runs on the instance during a deploy: `deploy-release.sh`, `apply_overrides.py` |
| `docker-compose.aws.yml`, `docker-compose.aws-rds.yml`, `Caddyfile.aws` | The AWS differences from the VPS stack, and nothing else |

---

## What it costs

Approximate on-demand list prices in us-east-1. They are estimates, not
quotes: confirm them on the AWS pricing pages (or the AWS Pricing Calculator)
before relying on them, and note that free-tier terms differ between older and
newer accounts.

| Item | Running | Stopped (`scripts/stop.sh`) |
|---|---|---|
| EC2 t4g.small | ~$0.0168/hr (~$12/month) | $0 |
| EBS gp3, 30 GB | ~$2.40/month | ~$2.40/month |
| Elastic IP (every public IPv4 address bills) | ~$3.60/month | ~$3.60/month |
| RDS db.t4g.micro + 20 GB, only with `use_rds` | ~$0.016/hr + ~$2.30/month | storage only, **and it restarts itself after 7 days** |
| CloudFront, S3, CloudWatch, SNS, SSM | cents at this traffic; mostly inside the free tier | same |
| Budget, dashboard (first 3), alarms (first 10) | free | free |

Roughly **$18/month left running, ~$6/month stopped, $0 after teardown.**
An afternoon of experimenting costs well under a dollar. The budget in
`budget.tf` mails you at 50% of the limit you set, and when the forecast
passes 100%.

Deliberately absent, because each would add a fixed monthly cost to a stack
with no traffic: NAT gateway (~$33), Application Load Balancer (~$16),
Multi-AZ RDS (double), WAF (~$5 + rules).

---

## Prerequisites

On your machine (the scripts are bash: Linux, macOS, or **Git Bash on
Windows**):

1. **An AWS account** and credentials for the AWS CLI with enough rights to
   create everything here. An admin profile or an IAM Identity Center (SSO)
   session is simplest for a learning account. Check with
   `aws sts get-caller-identity`.
2. **AWS CLI v2**.
3. **Terraform 1.6+**.
4. **Node.js 20+ and npm** (the frontend is built locally).
5. **Python 3.8+** (already a requirement of this repo).
6. **The Session Manager plugin** for the AWS CLI, only for `scripts/shell.sh`.
7. **git**, with this repo checked out.

You do **not** need a domain, an SSH key, Docker locally, or anything
installed on the instance by hand.

On Linux or macOS, if `aws/scripts/up.sh` says "permission denied", the
executable bit did not survive the checkout: `chmod +x aws/scripts/*.sh`, or
run any of them as `bash aws/scripts/up.sh`. (When committing from Windows,
`git add --chmod=+x aws/scripts/*.sh aws/instance/*.sh` records it.)

---

## Stand it up

```bash
# 1. Configure
cp aws/terraform/terraform.tfvars.example aws/terraform/terraform.tfvars
#    edit terraform.tfvars: set alert_email (the only required value)

# 2. Create the infrastructure (5-10 min; CloudFront is the slow part)
aws/scripts/up.sh

# 3. Confirm the "AWS Notification - Subscription Confirmation" mail.
#    Until you click it, alarms fire at nobody.

# 4. Ship the app (first backend build: 10-15 min on the instance)
aws/scripts/deploy.sh

# 5. Open the app_url that up.sh and deploy.sh print
```

Then prove each piece works:

| Check | How |
|---|---|
| The app loads, sign-in and chat work | Open `app_url`, use "Try the demo" |
| Uploads reach S3 and come back through CloudFront | Upload an avatar on your profile card, then open the image's URL: it is `/media/avatars/...webp` on the CloudFront host |
| Voice media reaches the instance | Join a voice channel from two browsers. Audio flowing proves 7882/udp is open; it never passes through CloudFront |
| Logs leave the box | `aws/scripts/logs.sh rest_api` |
| The alarm pages you | `aws/scripts/test-alarm.sh` (below) |

---

## Day to day

| Script | Does |
|---|---|
| `up.sh` | Plan and apply Terraform. Re-run after editing any `.tf` or `terraform.tfvars` |
| `deploy.sh` | `deploy-backend.sh` then `deploy-frontend.sh` |
| `deploy-backend.sh` | Packages your working tree (**uncommitted changes included**, gitignored files excluded), uploads it to S3, and has the instance build and start it via SSM Run Command |
| `deploy-frontend.sh` | `npm run build`, sync to S3 with long-lived caching for hashed assets, invalidate `index.html` |
| `status.sh` | Instance and database state, alarm states, container health, disk and memory |
| `logs.sh [service \| command-id]` | Tail CloudWatch Logs: everything, one service, or one deploy's full output |
| `shell.sh` | A shell on the instance through Session Manager (no SSH) |
| `stop.sh` / `start.sh` | Stop paying for compute; data and addresses survive |
| `test-alarm.sh` | Fire the error alarm through the real log path |
| `teardown.sh` | Destroy everything, then verify nothing billable is left |

**A deploy, step by step** (`instance/deploy-release.sh`):

1. Reads its configuration and secrets from SSM Parameter Store.
2. On the **first** deploy only, runs `generate_env_files.py` to create the
   application's own secrets (JWT key, LiveKit secret). They never leave the
   instance, as on the VPS.
3. `apply_overrides.py` points the env files at AWS: S3 storage, and RDS if
   enabled.
4. `check_config.py --prod` must pass, the same gate the VPS uses, before
   anything restarts.
5. `docker compose up -d --build`, then waits for every health check.
6. Only then marks the release current. Keeps three releases.

### Firing the alarm for real

```bash
aws/scripts/test-alarm.sh
```

This writes an error-level JSON line through the same Docker `awslogs`
driver the services use, so it exercises every hop: container → CloudWatch
Logs → metric filter → `ErrorLogLines` → alarm → SNS → your inbox. Expect the
ALARM mail within about five minutes and an OK mail after that.
`aws cloudwatch set-alarm-state` would only prove that SNS can send mail.

### Measuring the websocket path

tasks.md said not to put the websocket or LiveKit signalling behind
CloudFront without measuring it. They are behind it here (see
[why](#one-hostname-routed-by-path)), so measure it:

1. In the browser devtools Network tab, filter to WS, open `/ws`, and send a
   message: the frame round trip is the chat latency through CloudFront.
2. Compare it with the same measurement against the VPS.
3. Join a voice channel and note the time from click to "connected". That is
   the signalling path. Audio latency does not change either way, since media
   goes straight to the instance over UDP.

If the numbers are bad, the fix is a second hostname for `/ws` and
`/livekit` that points at the instance directly with its own certificate,
which needs a domain.

---

## Tear it down

```bash
aws/scripts/teardown.sh
```

It asks once, runs `terraform destroy` (10-20 minutes, mostly CloudFront),
and then **checks** rather than trusts: anything still tagged
`Project=project-rain`, unattached Elastic IPs, EBS volumes and snapshots,
and the log group. It ends with "Clean" or with a list.

**Everything goes**: uploaded images, the database, every message. Check the
Billing console a day later: a partial day of charges is normal, and a new
one is not.

---

## How each piece works, and why

### One hostname, routed by path

CloudFront has three origins and routes by path: `/api/*`, `/ws*` and
`/livekit/*` go to the instance and are never cached; `/media/*` goes to the
media bucket; everything else goes to the frontend bucket.

The browser app assumes it shares an origin with the API: the refresh cookie
is scoped to `/api/auth`, and nothing sends CORS headers. Keeping one hostname
means **no application change**, and it means the stack needs no domain,
because CloudFront's own certificate covers `*.cloudfront.net`.

Uploaded images use the same trick. Every stored image is at
`/media/{key}` on both the VPS (Caddy serves a volume) and AWS (CloudFront
serves the bucket), so the database, the event payloads and the frontend never
know which backend is running. `STORAGE_BACKEND=s3` is the only switch.

### The SPA rewrite is a CloudFront Function, not an error page

Reloading `/dm/123` asks S3 for an object that does not exist. The common
fix, a distribution-wide custom error response that maps 403/404 to
`index.html`, would also rewrite the API's own 404s ("you are not a member")
into 200 HTML pages. `terraform/functions/spa-rewrite.js` runs only on the
frontend behaviour instead.

### The origin only answers CloudFront

Two locks, because either alone is not enough:

1. The security group admits port 80 only from AWS's managed prefix list of
   CloudFront origin-facing addresses.
2. Caddy refuses any request without the `X-Origin-Verify` secret that this
   distribution adds. Another person's CloudFront distribution comes from the
   same address ranges, so lock 1 alone would let it through.

The secret is generated by Terraform and handed to the instance through SSM.
It is never in the repo or in user data.

### No SSH at all

Port 22 is closed and there is no key pair. Deploys use **SSM Run Command**
and shells use **Session Manager**. Both are IAM-authorised API calls, logged
in CloudTrail, with nothing to leak or rotate.

### Credentials on the box

The instance has a role and no access keys. rest_api's boto3 (uploads), the
awslogs driver and the AWS CLI all fetch short-lived credentials from the
metadata service. The role can write only under `media/` in the media bucket,
read only `releases/` in the artifacts bucket, write only to its own log
group, and read only its own SSM path.

### Secrets

| Secret | Created by | Lives in |
|---|---|---|
| JWT key, LiveKit secret, local Postgres password | `generate_env_files.py`, first deploy | `/opt/rain/shared/*.env` on the instance (mode 600), nowhere else |
| RDS password, origin secret | Terraform | SSM SecureString **and Terraform state** |

Terraform state therefore holds secrets in plain text. It is local
(`aws/terraform/terraform.tfstate`) and gitignored. To move it to S3 with
locking, add a `backend "s3"` block to `versions.tf` (Terraform 1.11+
supports `use_lockfile = true` with no DynamoDB table) and run
`terraform init -migrate-state`.

### Logs and alarms

Containers log straight to CloudWatch through Docker's `awslogs` driver:
there is no agent to run and nothing is written to disk, which is the
log-rotation problem the VPS still has. The driver is non-blocking, so a
CloudWatch outage drops log lines rather than freezing the app.

The services log JSON in production, so a metric filter on
`$.level = "error"` counts errors without parsing text. Alarms:

| Alarm | Fires when | Does |
|---|---|---|
| `app-errors` | any service logs an error | mails you |
| `instance-system-check` | AWS hardware under the instance fails | **moves the instance to new hardware** (same id, disk, address), and mails you |
| `instance-check` | the instance's own OS check fails | mails you |
| `cpu-credits-low` | burst credits nearly gone | mails you, before it slows to 20% CPU |

The dashboard (`dashboard_url` output) shows errors, CPU and credits,
network (including all voice media), CloudFront requests and 5xx rate, and a
table of recent error lines.

---

## Gotchas this stack already handles

Each of these is a real failure you would otherwise meet, with the reason
written next to the setting that avoids it.

| Symptom you would have seen | Cause | Handled in |
|---|---|---|
| Uploads fail with `NoCredentialsError` while every `aws` command on the host works | IMDSv2's default hop limit of 1 cannot reach a container on the Docker bridge | `ec2.tf`: `http_put_response_hop_limit = 2` |
| Voice connects, then nobody hears anyone | UDP 7882 not open; signalling works through CloudFront, media cannot | `security.tf` |
| An unexpected CPU charge on a burstable instance | t4g defaults to "unlimited" credits | `ec2.tf`: `cpu_credits = "standard"` + alarm |
| Adding a security group rule fails with a quota error | The CloudFront prefix list counts as ~55 of the 60 rules | Noted in `security.tf`; the group stays small |
| `terraform destroy` stops half way and keeps billing | Non-empty buckets | `s3.tf`: `force_destroy` |
| Deep links 404, or API 404s come back as HTML | Distribution-wide error pages | `functions/spa-rewrite.js` |
| A stopped RDS database is billing again | AWS restarts stopped databases after 7 days | Warned in `stop.sh` |
| RDS refuses the connection with a pg_hba error | `rds.force_ssl = 1` by default on Postgres 15+ | asyncpg negotiates TLS by default; noted in `rds.tf` |
| Git Bash turns `/project-rain/poc` into `C:/Program Files/Git/project-rain/poc` | MSYS path conversion | `scripts/lib.sh` |
| The first image build is killed with no clear error | 2 GB RAM | 2 GB swap in user data |
| A new AMI replaces the instance and its database | Terraform tracks the AMI | `ec2.tf`: `ignore_changes = [ami, user_data]` |
| CloudFront, S3 and SSM names collide with someone else's copy of this repo | Bucket names are global | Random suffix in `main.tf` |

---

## Troubleshooting

**`deploy-backend.sh` says the bootstrap has not finished.** User data is
still installing Docker (a few minutes after the first `up.sh`). Read
`/var/log/project-rain-bootstrap.log` through `shell.sh`, or the instance's
system log in the EC2 console.

**A deploy failed.** The last 60 lines are printed; `logs.sh <command-id>`
has all of it. A `check_config.py` failure names the mismatched setting and
never prints values.

**The app answers 502 or 504.** CloudFront cannot reach the instance: it is
stopped (`start.sh`), still booting, or the containers are unhealthy
(`status.sh`).

**The app answers 403 "Forbidden" from the instance.** The origin secret did
not match. Terraform re-created it (for example after a taint) and the
instance still has the old one: run `deploy-backend.sh` so the instance
re-reads SSM.

**A frontend change does not show.** `deploy-frontend.sh` invalidates
`index.html`; a hard reload covers a browser that cached it anyway.

**Changing `use_rds` on a live stack.** Terraform creates or destroys the
database; **no data moves either way**. Redeploy afterwards so the env files
are pointed at the right host, then expect an empty database (the demo
account re-seeds itself).

---

## Beyond the proof of concept

What a production-grade version of this would change, roughly in order of
value, with what each costs to learn:

1. **Images built in CI, pushed to ECR**, and pulled by the instance instead of
   building on it. This is Phase 12's missing CD, and it would make every
   deploy a pull.
2. **ECS on Fargate, or an Auto Scaling group behind an ALB**, for more than one
   instance. Needs everything in AGENTS.md's replica list first
   (`GRPC_ADVERTISE_HOST`, gateway deregistration, endpoint expiry), and
   LiveKit then needs its own host or its Redis-backed multi-node mode.
3. **ElastiCache for Redis** and **RDS Multi-AZ**, so the stateful pieces
   survive an instance or an availability zone.
4. **A domain in Route 53** with an ACM certificate (the variables already
   exist), and HTTPS from CloudFront to the origin.
5. **Signed CloudFront URLs for `/media`**, if attachments in DMs should not be
   readable by anyone who has the link. Today, like the VPS, an attachment URL
   is unguessable but not access-controlled.
6. **WAF** on the distribution, with rate-based rules. That is Phase 20
   (abuse limits) at the edge instead of in the app.
