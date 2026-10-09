"""Point generated env files at AWS. Runs on the instance, on every deploy.

generate_env_files.py writes the VPS shape: local Postgres, local media, and
it generates every secret. On AWS three things differ, and they are set here
rather than by a second generator, so the VPS and AWS stacks can never drift
apart in anything else:

- uploaded images go to S3 (STORAGE_BACKEND=s3 and the bucket);
- with RDS, Postgres is a hostname and a password Terraform created;
- LiveKit's webhook signs with the key rest_api verifies (livekit.yaml).

Idempotent: re-running it rewrites the same lines. Every other line, comment
and secret in the files is left exactly as it was.

    python3.11 apply_overrides.py /opt/rain/shared   (settings from the environment)

Stdlib only, like check_config.py, because it runs on the host.
"""

import os
import re
import sys
from pathlib import Path


def set_values(path: Path, values: dict[str, str]) -> None:
    """Replace KEY=... lines in a docker env_file, appending any that are missing."""
    lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(values)
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    out.extend(f"{key}={value}" for key, value in remaining.items())

    # Written beside and renamed over, so a crash mid-write cannot leave a
    # half-written file holding the only copy of the secrets.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def livekit_yaml(shared: Path, template: Path) -> None:
    """livekit.yaml from the prod example, signing webhooks with rest_api's key."""
    target = shared / "livekit.yaml"
    api_key = read_env(shared / "rest_api.env").get("LIVEKIT_API_KEY", "")
    if not api_key:
        sys.exit("rest_api.env has no LIVEKIT_API_KEY; was generate_env_files.py run?")
    text = template.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^(\s*api_key:\s*).*$", rf"\g<1>{api_key}", text)
    target.write_text(text, encoding="utf-8")


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def main() -> None:
    shared = Path(sys.argv[1])
    release = Path(__file__).resolve().parents[2]
    env = os.environ

    set_values(
        shared / "rest_api.env",
        {
            "STORAGE_BACKEND": "s3",
            "S3_BUCKET": env["RAIN_MEDIA_BUCKET"],
            "S3_REGION": env["AWS_REGION"],
        },
    )

    if env.get("RAIN_USE_RDS") == "true":
        credentials = {
            "POSTGRES_USER": env["RAIN_DB_USER"],
            "POSTGRES_PASSWORD": env["RAIN_DB_PASSWORD"],
            "POSTGRES_DB": env["RAIN_DB_NAME"],
        }
        location = {"POSTGRES_HOST": env["RAIN_DB_HOST"], "POSTGRES_PORT": "5432"}
        for service in ("rest_api", "ws_gateway"):
            set_values(shared / f"{service}.env", {**credentials, **location})
        # The container is not started with RDS, but check_config.py compares
        # all three files, and a stale password here would fail the deploy.
        set_values(shared / "postgres.env", credentials)

    livekit_yaml(shared, release / "livekit.example.yaml")
    print("applied AWS overrides")


if __name__ == "__main__":
    main()
