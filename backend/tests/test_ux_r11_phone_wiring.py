"""ux-r11: the deferred phone request is really connected in the API and the bot entry points.

A fresh interpreter imports the real entry module (the way the server / bot start) and we
ask SQLAlchemy whether the commit listener is registered. Importing the service module
inside the test process would prove nothing.
"""

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent

PROBE_NOT_IMPORTED = "import sys, {entry}; print('app.services.deferred_phone_prompt' in sys.modules)"


@pytest.mark.parametrize("entry", ["app.main", "bot.main"])
def test_entry_point_registers_phone_request_listener(entry: str) -> None:
    out = subprocess.run(
        [sys.executable, "-c", PROBE_NOT_IMPORTED.format(entry=entry)],
        cwd=BACKEND, capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr[-800:]
    assert out.stdout.strip() == "True", f"{entry} does not connect the phone request"
