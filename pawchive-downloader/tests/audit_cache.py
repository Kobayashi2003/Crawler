"""Does a corrupt/truncated cache silently lose download state?"""
import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import Cache, Storage, Downloader, Logger, API
from src.core.models import Config, Artist

ok = True
def check(label, got, want):
    global ok; ok &= (got == want)
    print(f"{'PASS' if got==want else 'FAIL'}  {label}: {got!r}")

work = tempfile.mkdtemp(prefix="paw_audit_")
cfg = Config(cache_dir=os.path.join(work, "c"), logs_dir=os.path.join(work, "l"),
             data_dir=os.path.join(work, "d"), retry_delay=0)
log = Logger(cfg.logs_dir); st = Storage(cfg.data_dir)
ca = Cache(cfg.cache_dir, log, cfg, st); api = API(log, cfg)
dl = Downloader(cfg, log, st, ca, api)

POSTS = [
    {"id": "1", "user": "u", "service": "fanbox", "published": "2020-01-01T00:00:00"},
    {"id": "2", "user": "u", "service": "fanbox", "published": "2021-01-01T00:00:00"},
    {"id": "3", "user": "u", "service": "fanbox", "published": "2026-01-01T00:00:00"},
]
api.get_profile_until_success = lambda s, u: {"id": "u", "name": "N", "service": "fanbox",
                                             "updated": "2026-01-01"}
api.get_all_posts = lambda s, u: POSTS

# Artist added long ago with a last_date; posts 1&2 were downloaded, 3 is pending.
art = Artist(id="fanbox_u", service="fanbox", user_id="u", name="N",
             last_date="2025-01-01T00:00:00")
st.save_artist(art)
dl.update_posts(art)
ca.update_post(art.id, "1", done=True)
ca.update_post(art.id, "2", done=True)
before = ca.stats(art.id)
check("baseline", (before["done"], before["pending"]), (2, 1))

# --- simulate a crash halfway through a cache write (write_text is not atomic) ---
path = os.path.join(cfg.cache_dir, "fanbox_u_posts.json")
full = open(path, encoding="utf-8").read()
open(path, "w", encoding="utf-8").write(full[: len(full) // 2])   # truncated JSON

from src.common.jsonio import CorruptJSON
try:
    ca.load_posts(art.id, apply_filters=False)
    check("corrupt cache raises", False, True)
except CorruptJSON:
    check("corrupt cache raises instead of reading as []", True, True)

# a sync on top of a corrupt cache must refuse, not rewrite
try:
    dl.update_posts(art)
    check("update_posts refuses on corrupt cache", False, True)
except CorruptJSON:
    check("update_posts refuses on corrupt cache", True, True)
check("corrupt file left untouched", len(open(path, encoding="utf-8").read()), len(full)//2)
check("stats reports corrupt", ca.stats(art.id).get("corrupt"), True)

# restore and confirm state survived
open(path, "w", encoding="utf-8").write(full)
after_restore = ca.stats(art.id)
check("state intact after restore", (after_restore["done"], after_restore["pending"]), (2, 1))
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
