"""Tests for the root `check_config.py` ops script.

It is loaded by path rather than imported, because it lives at the repository
root on purpose: it has to run on the VPS with nothing installed.

    python -m unittest discover -s backend/tests/unit
"""

import importlib.util
import io
import os
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parents[3]


def load_checker():
    """A fresh module each time, since it accumulates failures in globals."""
    spec = importlib.util.spec_from_file_location(
        "check_config", ROOT / "check_config.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHARDS = {"rest_api": 2, "ws_gateway": 2, "lease_manager": 2}


def write_deployment(directory, shards=None, secret="s3cret", livekit_secret="lk"):
    shards = SHARDS if shards is None else shards
    files = {
        "rest_api": [
            f"SECRET_KEY={secret}",
            "ALGORITHM=HS256",
            "POSTGRES_USER=rain",
            "POSTGRES_PASSWORD=pw",
            "POSTGRES_DB=raindb",
            "REDIS_HOST=redis",
            "REDIS_PORT=6379",
            "REDIS_DB=0",
            "LIVEKIT_API_KEY=rainkey",
            f"LIVEKIT_API_SECRET={livekit_secret}",
        ],
        "ws_gateway": [
            "SECRET_KEY=s3cret",
            "ALGORITHM=HS256",
            "POSTGRES_USER=rain",
            "POSTGRES_PASSWORD=pw",
            "POSTGRES_DB=raindb",
            "REDIS_HOST=redis",
            "REDIS_PORT=6379",
            "REDIS_DB=0",
        ],
        "event_consumer": ["REDIS_HOST=redis", "REDIS_PORT=6379", "REDIS_DB=0"],
        "lease_manager": ["REDIS_HOST=redis", "REDIS_PORT=6379", "REDIS_DB=0"],
        "postgres": [
            "POSTGRES_USER=rain",
            "POSTGRES_PASSWORD=pw",
            "POSTGRES_DB=raindb",
        ],
        "livekit": ["LIVEKIT_KEYS=rainkey: lk"],
    }
    for service, lines in files.items():
        if service in shards:
            name, value = shards[service]  # type: ignore[misc]
            lines = lines + [f"{name}={value}"]
        (directory / f"{service}.env").write_text("\n".join(lines) + "\n")


class CheckConfig(unittest.TestCase):
    def run_checker(self, shards=None, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            directory = pathlib.Path(tmp)
            if shards is not None:
                shards = {k: ("NUM_SHARDS", v) for k, v in shards.items()}
            else:
                shards = {k: ("NUM_SHARDS", v) for k, v in SHARDS.items()}
            write_deployment(directory, shards, **kwargs)
            cwd = os.getcwd()
            os.chdir(directory)
            try:
                checker = load_checker()
                out = io.StringIO()
                with redirect_stdout(out):
                    code = checker.main(["--prod"])
                return code, out.getvalue(), checker
            finally:
                os.chdir(cwd)

    def test_a_consistent_deployment_passes(self):
        code, output, _ = self.run_checker()
        self.assertEqual(code, 0, output)

    def test_a_shard_mismatch_fails(self):
        """The one this exists for: rest_api publishing onto unleased shards."""
        code, output, checker = self.run_checker(
            {"rest_api": 16, "ws_gateway": 2, "lease_manager": 2}
        )
        self.assertEqual(code, 1)
        self.assertTrue(any("disagree" in f for f in checker.FAILURES), output)

    def test_a_missing_shard_count_in_rest_api_fails(self):
        code, output, checker = self.run_checker({"ws_gateway": 2, "lease_manager": 2})
        self.assertEqual(code, 1)
        self.assertTrue(any("rest_api" in f for f in checker.FAILURES), output)

    def test_the_legacy_name_passes_with_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = pathlib.Path(tmp)
            write_deployment(
                directory,
                {
                    "rest_api": ("NUM_SHARDS", 2),
                    "ws_gateway": ("NUM_SHARDS", 2),
                    "lease_manager": ("NUM_STREAMS", 2),
                },
            )
            cwd = os.getcwd()
            os.chdir(directory)
            try:
                checker = load_checker()
                with redirect_stdout(io.StringIO()):
                    code = checker.main(["--prod"])
            finally:
                os.chdir(cwd)
        self.assertEqual(code, 0)
        self.assertTrue(any("deprecated" in w for w in checker.WARNINGS))

    def test_a_mismatched_jwt_secret_fails(self):
        code, output, checker = self.run_checker(secret="different")
        self.assertEqual(code, 1)
        self.assertTrue(any("SECRET_KEY" in f for f in checker.FAILURES), output)

    def test_a_mismatched_livekit_secret_fails(self):
        code, output, checker = self.run_checker(livekit_secret="stale")
        self.assertEqual(code, 1)
        self.assertTrue(any("LIVEKIT" in f for f in checker.FAILURES), output)


if __name__ == "__main__":
    unittest.main()
