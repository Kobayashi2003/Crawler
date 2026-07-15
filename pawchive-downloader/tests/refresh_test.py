import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import Cache, Storage, Downloader, Logger, API
from src.core.models import Config, Artist, Post

work = tempfile.mkdtemp(prefix="paw_rt_")
cfg = Config(cache_dir=os.path.join(work, "c"), logs_dir=os.path.join(work, "l"),
             data_dir=os.path.join(work, "d"), retry_delay=0)
log = Logger(cfg.logs_dir); st = Storage(cfg.data_dir)
dl = Downloader(cfg, log, st, Cache(cfg.cache_dir, log, cfg, st), API(log, cfg))

def post(atts, file=None, done=True, edited=None):
    return Post(id="1", user="u", service="fanbox", file=file, attachments=list(atts),
                done=done, edited=edited)

ok = True
def check(label, got, want):
    global ok
    ok &= (got == want)
    print(f"{'PASS' if got == want else 'FAIL'}  {label}: {got}")

# 1. re-scrape: same files, new content-hash paths -> refresh paths, DON'T re-download
p = post([{"name": "a.png", "path": "/old/1"}, {"path": "/old/2"}])
flag = dl._refresh(p, {"id": "1", "attachments": [{"name": "a.png", "path": "/new/1"}, {"path": "/new/2"}]}, False)
check("path-only change re-flags?", flag, False)
check("  ...but paths refreshed", [a["path"] for a in p.attachments], ["/new/1", "/new/2"])
check("  ...still done", p.done, True)

# 2. a genuinely new attachment (25 -> 26) -> re-download
p = post([{"path": f"/old/{i}"} for i in range(25)])
flag = dl._refresh(p, {"id": "1", "attachments": [{"path": f"/new/{i}"} for i in range(26)]}, False)
check("count 25->26 (missing file) re-flags?", flag, True)
check("  ...undone", p.done, False)
check("  ...adopted 26", len(p.attachments), 26)

# 3. same count, different names (kemono names vs paw names) -> NO re-download
p = post([{"name": "kem.jpeg", "path": "/x"}])
flag = dl._refresh(p, {"id": "1", "attachments": [{"name": "paw.jpeg", "path": "/y"}]}, False)
check("same-count rename re-flags?", flag, False)
check("  ...but adopted paw metadata", p.attachments[0]["name"], "paw.jpeg")

# 3b. fewer files upstream on a plain sync -> KEEP local, never shrink
p = post([{"path": "/a"}, {"path": "/b"}])
flag = dl._refresh(p, {"id": "1", "attachments": [{"path": "/a2"}]}, False)
check("fewer files re-flags?", flag, False)
check("  ...local set kept (not shrunk)", len(p.attachments), 2)
check("  ...still done", p.done, True)

# 3c. deep sync accepts a genuine upstream removal
p = post([{"path": "/a"}, {"path": "/b"}])
dl._refresh(p, {"id": "1", "edited": "x", "attachments": [{"path": "/a2"}]}, True)
check("deep sync accepts removal", len(p.attachments), 1)

# 4. empty remote file set must NOT erase local, must NOT re-flag
p = post([{"path": "/keep/1"}, {"path": "/keep/2"}])
flag = dl._refresh(p, {"id": "1", "attachments": []}, False)
check("empty remote re-flags?", flag, False)
check("  ...local kept", len(p.attachments), 2)
check("  ...still done", p.done, True)

# 5. edited timestamp only: plain sync ignores, deep sync re-downloads
p = post([{"path": "/a"}], edited=None)
check("edited-only, plain sync", dl._refresh(p, {"id": "1", "edited": "2026-01-01", "attachments": [{"path": "/a"}]}, False), False)
p = post([{"path": "/a"}], edited=None)
check("edited-only, deep sync", dl._refresh(p, {"id": "1", "edited": "2026-01-01", "attachments": [{"path": "/a"}]}, True), True)

# 6. an already-undone post: paths refresh, no double-count
p = post([{"path": "/old"}], done=False)
flag = dl._refresh(p, {"id": "1", "attachments": [{"path": "/new"}]}, False)
check("undone post counted as edited?", flag, False)
check("  ...paths still refreshed", p.attachments[0]["path"], "/new")

print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
