import sys, os, tempfile, threading, http.server, socketserver, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import API, Logger, Storage, Cache, Downloader
from src.core.api import TransientAPIError
from src.core.models import Config, Artist, Post

work = tempfile.mkdtemp(prefix="paw_safe_")
for v in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"): os.environ.pop(v, None)
BODY = b"Z" * 200000
hits = {"get": 0}

class H(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        if self.path == "/nolen": self.send_response(200); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length", str(len(BODY))); self.end_headers()
    def do_GET(self):
        hits["get"] += 1
        if self.path == "/503":
            self.send_response(503); self.send_header("Content-Length", "0"); self.end_headers(); return
        if self.path == "/nolen":            # no Content-Length anywhere
            self.send_response(200); self.end_headers(); self.wfile.write(BODY); return
        self.send_response(200); self.send_header("Content-Length", str(len(BODY))); self.end_headers()
        self.wfile.write(BODY)
    def log_message(self, *a): pass

srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H); srv.daemon_threads = True
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}"

ok = True
def check(label, got, want):
    global ok; ok &= (got == want)
    print(f"{'PASS' if got==want else 'FAIL'}  {label}: {got}")

# 1. file download retries are BOUNDED (503 forever) and give up
cfg = Config(retry_delay=0, max_retries=0, download_max_retries=3, logs_dir=os.path.join(work,"l"))
api = API(Logger(cfg.logs_dir), cfg); api.session.trust_env = False
hits["get"] = 0
t0 = time.time()
try:
    api.download_file_until_success(f"{base}/503", os.path.join(work, "a.bin"))
    check("bounded download retry raises", False, True)
except Exception as e:
    check("bounded download retry raises", type(e).__name__ != "", True)
check("  ...gave up after 3 GETs", hits["get"], 3)
check("  ...did not hang", time.time() - t0 < 10, True)

# 2. API requests are UNLIMITED (max_retries=0): succeed after transient failures
calls = {"n": 0}
def flaky():
    calls["n"] += 1
    if calls["n"] < 4: raise TransientAPIError("boom")
    return "ok"
check("api retries forever until success", api._retry(flaky, "x"), "ok")
check("  ...took 4 attempts", calls["n"], 4)

# 3. unverifiable download must NOT destroy an existing file
d = os.path.join(work, "keep"); os.makedirs(d)
target = os.path.join(d, "f.bin")
open(target, "wb").write(b"ORIGINAL")
api.download_file(f"{base}/nolen", target, raise_on_error=True)
check("existing file preserved when size unverifiable", open(target, "rb").read(), b"ORIGINAL")
check("  ...no temp left", [f for f in os.listdir(d) if f.endswith(".part")], [])

# 4. stale .part files are swept once per artist, before any post thread starts
st = Storage(os.path.join(work, "data")); cfg2 = st.load_config()
cfg2.download_dir = os.path.join(work, "dl"); cfg2.retry_delay = 0
ca = Cache(os.path.join(work, "c"), Logger(cfg.logs_dir), cfg2, st)
dl = Downloader(cfg2, Logger(cfg.logs_dir), st, ca, api)
a = Artist(id="fanbox_x", service="fanbox", user_id="x", name="N"); st.save_artist(a)
p = Post(id="1", user="x", service="fanbox", title="t", published="2026-01-01T00:00:00",
         attachments=[{"path": "/a/b/c.png"}])
ca.save_posts(a.id, [p])
from src.core.formatter import Formatter
from src.core.files import extract_files
sd = os.path.join(cfg2.download_dir,
                  str(Formatter.artist_folder(a, cfg2.artist_folder_template)),
                  Formatter.post_folder(p, cfg2.post_folder_template, cfg2.date_format))
os.makedirs(sd, exist_ok=True)
orphan = os.path.join(sd, ".0.png.deadbeef.part"); open(orphan, "wb").write(b"junk")
api.download_file_until_success = lambda url, path, on_progress=None: True
dl._download_posts(a, [p])
check("orphan .part swept", os.path.exists(orphan), False)

# 5. remote `edited=null` is neither an edit nor allowed to erase local
p = Post(id="1", user="x", service="fanbox", edited="2026-01-01", done=True,
         attachments=[{"path": "/a"}])
flag = dl._refresh(p, {"id": "1", "edited": None, "attachments": [{"path": "/a2"}]}, True)
check("remote edited=null re-flags?", flag, False)
check("  ...local edited preserved", p.edited, "2026-01-01")

srv.shutdown()
print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
