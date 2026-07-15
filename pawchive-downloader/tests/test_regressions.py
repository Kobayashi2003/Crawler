"""Runs each regression script in its own interpreter.

The scripts mutate global state (cwd, PAWCHIVE_* env vars, monkeypatched API
methods, deliberately-stuck threads), so subprocess isolation is required —
do not import them into one pytest process.
"""
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

SCRIPTS = [
    "audit_cache.py",
    "cancel_test.py",
    "dedupe_test.py",
    "env_test.py",
    "flap_test.py",
    "links_test.py",
    "notfound_test.py",
    "refresh_test.py",
    "safety_test.py",
]


@pytest.mark.parametrize("script", SCRIPTS)
def test_regression(script):
    result = subprocess.run(
        [sys.executable, str(HERE / script)],
        cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    if result.returncode != 0:
        pytest.fail(
            f"{script} exited {result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
