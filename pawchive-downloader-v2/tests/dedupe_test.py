"""The cover-repeated-as-attachment case must not download twice or re-flag."""
import sys, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.core.files import extract_files, unusable_files
from src.core.models import Post
from src.core.downloader import Downloader

COVER = "/6c/61/6c618b9d.jpeg"
OTHER = "/aa/bb/aabbccdd.png"
fails = []


def check(name, cond):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        fails.append(name)


def post(**kw):
    return Post(id="1", user="u", service="fanbox", **kw)


print("extract_files")
p = post(file={"path": COVER, "name": "cover.jpeg"},
         attachments=[{"path": COVER, "name": "0.jpeg"}, {"path": OTHER, "name": "1.png"}])
files = extract_files(p)
check("cover repeated as attachment yields one entry", len(files) == 2)
check("first occurrence wins its name", files[0]["name"] == "cover.jpeg")
check("distinct paths preserved in order", [f["path"] for f in files] == [COVER, OTHER])

p2 = post(file={"path": COVER}, attachments=[{"path": OTHER}, {"path": OTHER}])
check("repeated attachment collapses", len(extract_files(p2)) == 2)

p3 = post(file=None, attachments=[{"name": "no-path.psd"}])
check("pathless entry is unusable, not silently dropped", unusable_files(p3) == ["no-path.psd"])
check("pathless entry is not downloadable", extract_files(p3) == [])


print("\n_refresh must not re-flag a complete post")
d = Downloader.__new__(Downloader)


class _Log:
    def __getattr__(self, _):
        return lambda **kw: None


d.logger = _Log()

# kemono imported: file only, no attachments, already downloaded.
local = post(file={"path": COVER, "name": "c.jpg"}, attachments=[], done=True, edited=None)
# pawchive lists the same bytes twice.
remote = {"file": {"path": COVER, "name": "c.jpeg"},
          "attachments": [{"path": COVER, "name": "0.jpeg"}],
          "edited": None, "title": "t", "content": ""}
changed = d._refresh(local, remote, detect_edits=False)
check("duplicate cover does not re-flag", changed is False and local.done is True)
check("paths still refreshed from remote", local.file["path"] == COVER)

# A genuinely new file must still re-flag.
local2 = post(file={"path": COVER}, attachments=[], done=True)
remote2 = {"file": {"path": COVER}, "attachments": [{"path": COVER}, {"path": OTHER}],
           "edited": None, "title": "t", "content": ""}
check("a real extra file still re-flags",
      d._refresh(local2, remote2, detect_edits=False) is True and local2.done is False)

# An empty remote file set must never erase.
local3 = post(file={"path": COVER}, attachments=[], done=True)
check("empty remote set never erases",
      d._refresh(local3, {"file": None, "attachments": [], "title": "t"}, False) is False
      and local3.file is not None)

print("\n" + ("ALL PASS" if not fails else f"FAILURES: {fails}"))
sys.exit(1 if fails else 0)
