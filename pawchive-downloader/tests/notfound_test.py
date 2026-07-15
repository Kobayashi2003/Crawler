"""A 404 must give up; everything else must keep the unbounded retry."""
import sys, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
from src.core.api import API, PermanentAPIError
from src.core.models import Config
from src.common.logger import Logger

fails = []


def check(name, cond):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        fails.append(name)


def http_error(status):
    r = requests.Response()
    r.status_code = status
    return requests.exceptions.HTTPError(response=r)


cfg = Config(retry_delay=0, max_retries=0, not_found_max_retries=3)
api = API(Logger("logs"), cfg)

# 404 on an unbounded (API) retry must stop, not spin forever.
calls = []


def always_404():
    calls.append(1)
    raise http_error(404)


try:
    api._retry(always_404, "profile x/1")
    check("404 raises PermanentAPIError", False)
except PermanentAPIError:
    check("404 raises PermanentAPIError", True)
except Exception as e:
    check(f"404 raises PermanentAPIError (got {type(e).__name__})", False)
check(f"404 gave up after {len(calls)} attempts (cap=3)", len(calls) == 3)

# 503 must still retry without bound -- succeed on the 6th try, past any cap.
state = {"n": 0}


def flaky_503():
    state["n"] += 1
    if state["n"] < 6:
        raise http_error(503)
    return {"ok": True}


check("503 keeps retrying past the 404 cap", api._retry(flaky_503, "profile x/2") == {"ok": True})
check(f"503 succeeded on attempt {state['n']}", state["n"] == 6)

# A bounded (download) retry still gives up on a transient error.
state2 = {"n": 0}


def always_503():
    state2["n"] += 1
    raise http_error(503)


try:
    api._retry(always_503, "download f", max_attempts=4)
    check("bounded retry gives up", False)
except requests.exceptions.HTTPError:
    check("bounded retry gives up", True)
check(f"bounded retry used {state2['n']} attempts (cap=4)", state2["n"] == 4)

# A 404 on a bounded download retry stops at the 404 cap, not the download cap.
state3 = {"n": 0}


def dl_404():
    state3["n"] += 1
    raise http_error(404)


try:
    api._retry(dl_404, "download f", max_attempts=5)
except PermanentAPIError:
    pass
except Exception:
    pass
check(f"404 on download stops at 3, not 5 (used {state3['n']})", state3["n"] == 3)

print("\n" + ("ALL PASS" if not fails else f"FAILURES: {fails}"))
sys.exit(1 if fails else 0)
