"""An empty BOT_TOKEN would sign initData with an empty key (forgeable login).
config must refuse to import, always (also with SKIP_BOT_INIT)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def _import_config(token: str | None, **extra: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "BOT_TOKEN"}
    env["APP_PASS_SECRET"] = "x" * 32
    env.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:1/d")
    if token is not None:
        env["BOT_TOKEN"] = token
    env.update(extra)
    return subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )


@pytest.mark.parametrize("token", ["", "   ", "\t\n"])
@pytest.mark.parametrize("extra", [{}, {"SKIP_BOT_INIT": "1"}])
def test_blank_bot_token_refuses_to_start(token, extra):
    r = _import_config(token, **extra)
    assert r.returncode != 0
    assert "BOT_TOKEN" in r.stderr and "RuntimeError" in r.stderr


def test_non_empty_bot_token_ok():
    r = _import_config("123456:ABC-fake-token")
    assert r.returncode == 0, r.stderr
