import sys, os, json, tempfile, shutil
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

work = tempfile.mkdtemp(prefix="paw_env_")
os.chdir(work)
for k in list(os.environ):
    if k.startswith("PAWCHIVE_") or k in ("HTTPS_PROXY","HTTP_PROXY","ALL_PROXY"): del os.environ[k]

from src.common import env
from src.core.storage import Storage

ok = True
def check(label, got, want):
    global ok; ok &= (got == want)
    print(f"{'PASS' if got==want else 'FAIL'}  {label}: {got!r}")

# --- .env loader: real env wins, file fills the rest ---
open(".env", "w").write('# c\nPAWCHIVE_DOWNLOAD_DIR="X:/from-dotenv"\nHTTPS_PROXY=http://p:1\n')
os.environ["PAWCHIVE_DOWNLOAD_DIR"] = "Y:/from-real-env"
env.load_dotenv()
check("real env beats .env", os.environ["PAWCHIVE_DOWNLOAD_DIR"], "Y:/from-real-env")
check("quotes stripped from .env value", os.environ["HTTPS_PROXY"], "http://p:1")

# --- precedence: env > config.json > default ---
data = os.path.join(work, "data"); os.makedirs(data)
json.dump({"download_dir": "C:/from-config", "cache_dir": "C:/cache-from-config",
           "max_concurrent_files": 7},
          open(os.path.join(data, "config.json"), "w"))
st = Storage(data)
cfg = st.load_config()
check("env overrides config.json", cfg.download_dir, "Y:/from-real-env")
check("config.json used when no env", cfg.cache_dir, "C:/cache-from-config")
check("behaviour knob untouched by env", cfg.max_concurrent_files, 7)
check("defaults still apply", cfg.api_base, "https://pawchive.pw/api/v1")
check("data_dir reflects the real path", cfg.data_dir, data)

# --- DATA_DIR is env-only bootstrap ---
alt = os.path.join(work, "alt"); os.environ["PAWCHIVE_DATA_DIR"] = alt
st2 = Storage()
check("Storage() honours PAWCHIVE_DATA_DIR", str(st2.data_dir), alt)
del os.environ["PAWCHIVE_DATA_DIR"]

# --- save_config must not persist an env override, nor drop the file's value ---
cfg.max_concurrent_files = 9
st.save_config(cfg)
raw = json.load(open(os.path.join(data, "config.json")))
check("env value not written to config.json", raw["download_dir"], "C:/from-config")
check("edited behaviour knob persisted", raw["max_concurrent_files"], 9)
check("non-overridden path persisted", raw["cache_dir"], "C:/cache-from-config")

# a field env-overrides but that is NOT in the file must not be introduced
fresh = os.path.join(work, "fresh"); os.makedirs(fresh)
json.dump({"max_concurrent_files": 3}, open(os.path.join(fresh, "config.json"), "w"))
os.environ["PAWCHIVE_USER_AGENT"] = "envUA"
os.environ["PAWCHIVE_API_BASE"] = "https://env.example/api"
st3 = Storage(fresh)
cfg3 = st3.load_config()
check("env user_agent applied", cfg3.user_agent, "envUA")
check("env api_base applied", cfg3.api_base, "https://env.example/api")
st3.save_config(cfg3)
raw3 = json.load(open(os.path.join(fresh, "config.json")))
check("env-only user_agent not written", "user_agent" in raw3, False)
check("env-only api_base not written", "api_base" in raw3, False)
check("behaviour knob still written", raw3["max_concurrent_files"], 3)

# --- external tool paths ---
os.environ["PAWCHIVE_GDOWN_BIN"] = "/opt/gdown"
os.environ["PAWCHIVE_CLOUD_DIR"] = "/tmp/cloud"
from src.common.logger import Logger
from src.services.external_links import ExternalLinksDownloader
d = ExternalLinksDownloader(Logger(os.path.join(work, "l")))
check("gdown binary from env", d.gdown, "/opt/gdown")
check("cloud dir from env", str(d.out_dir), os.path.normpath("/tmp/cloud"))

os.chdir(REPO)
shutil.rmtree(work, ignore_errors=True)
print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
