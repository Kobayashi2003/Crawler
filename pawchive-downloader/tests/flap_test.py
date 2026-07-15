import sys, os, tempfile, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import API, Logger
from src.core.api import TransientAPIError
from src.core.models import Config

work = tempfile.mkdtemp(prefix="paw_flap_")

def page(n, off): return [{"id": str(off + i)} for i in range(n)]

def run(label, script, workers, expect, cap=200):
    api = API(Logger(os.path.join(work, "l")), Config(retry_delay=0, page_workers=workers))
    calls = {"n": 0, "per": {}}
    def fake(svc, uid, offset=0):
        calls["n"] += 1
        if calls["n"] > cap:
            raise RuntimeError(f"NO PROGRESS: exceeded {cap} requests (infinite loop)")
        k = calls["per"].get(offset, 0); calls["per"][offset] = k + 1
        seq = script.get(offset, [[]])
        r = seq[min(k, len(seq) - 1)]
        return r
    api.get_posts = fake
    try:
        got = api.get_all_posts("fanbox", "1")
    except RuntimeError as e:
        print(f"FAIL  {label}: {e}"); return False
    ids = [p["id"] for p in got]
    ok = len(got) == expect and len(set(ids)) == len(ids)
    print(f"{'PASS' if ok else 'FAIL'}  {label}: got={len(got)} expect={expect} requests={calls['n']}")
    return ok

ok = True
# offset 50 FLAPS: empty, data, empty, data, ... forever
flap = {0: [page(50,0)],
        50: [[], page(50,50), [], page(50,50), [], page(50,50)],
        100: [page(5,100)],
        150: [[]]}
for w in (1,4): ok &= run("flapping empty page at o=50", flap, w, 105)

# an offset that is ALWAYS empty on first ask, data on retry, repeatedly
flap2 = {0: [page(50,0)], 50: [[], page(50,50)], 100: [[], page(50,100)], 150: [page(3,150)], 200: [[]]}
for w in (1,4): ok &= run("two transient empties", flap2, w, 153)

# pathological: every page reports short (30) but data continues
short = {o: [page(30,o)] for o in range(0, 200, 50)}
short[200] = [[]]
for w in (1,4): ok &= run("every page short (30)", short, w, 120)

print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
