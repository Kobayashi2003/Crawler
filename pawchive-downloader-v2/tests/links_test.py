"""Reproduce the NFKC netloc crash and confirm the fix; check cancel-all wiring."""
import sys, io, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from urllib.parse import urlparse
from src.services.external_links import ExternalLinksExtractor
from src.cli.commands import COMMAND_MAP, cmd_cancel, cmd_cancel_all

fails = []


def check(name, cond):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        fails.append(name)


# The real post content: a URL immediately followed by Japanese, no space.
content = ("全体公開\nMUK(むっく)／MonsieuREnglish："
           "https://muk-monsieur.fanbox.cc/posts/123456全体公開MUK(むっく)／続き")

# 1. Faithful repro of the real crash: fullwidth '／' and '：' land in the netloc
# (no ASCII slash before them), and NFKC turns them into '/' and ':'.
crash_content = "MUK(むっく)／MonsieuREnglish：https://muk-monsieur全体公開MUK(むっく)／続き：https"
old_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
raised = False
for u in re.findall(old_pattern, crash_content):
    try:
        urlparse(u).netloc
    except ValueError:
        raised = True
check("old pattern produced a URL that crashes urlparse (repro)", raised)

# Same content must be safe under the new pattern.
for u in re.findall(ExternalLinksExtractor.URL_PATTERN, crash_content):
    try:
        urlparse(u).netloc
    except ValueError:
        check("new pattern never yields a crashing URL", False)
        break
else:
    check("new pattern never yields a crashing URL", True)

# 2. The new pattern stops at the first non-ASCII char.
ex = ExternalLinksExtractor.__new__(ExternalLinksExtractor)
new_urls = re.findall(ExternalLinksExtractor.URL_PATTERN, content)
check("new pattern still finds the link", len(new_urls) == 1)
check("new URL is ASCII-only (stops before Japanese)", new_urls[0].isascii())
check("new URL is the clean fanbox link",
      new_urls[0] == "https://muk-monsieur.fanbox.cc/posts/123456")

# 3. _parse never raises, even on a hand-built NFKC-hostile URL.
nasty = "https://muk-monsieur／abc：def/path"  # fullwidth / and :
try:
    scheme, netloc = ExternalLinksExtractor._parse(nasty)
    check("_parse does not raise on NFKC-hostile netloc", True)
    check("_parse returns https scheme", scheme == "https")
except Exception as e:
    check(f"_parse does not raise (got {e!r})", False)

# 4. cancel is single, cancel-all is bulk -- distinct handlers.
# COMMAND_MAP values are Command records; the handler function sits on .handler.
check("cancel -> single handler", COMMAND_MAP["cancel"].handler is cmd_cancel)
check("cancel-all -> bulk handler", COMMAND_MAP["cancel-all"].handler is cmd_cancel_all)

# 5. links_filter semantics (the de-hardcoded kemono mechanism):
# domain whitelist + reviewed artists hidden up to a cutoff date.
from src.services.external_links import make_link_filter
from src.core.models import ExternalLink


def L(**kw):
    base = dict(url="https://mega.nz/file/x", domain="mega.nz", protocol="https",
                post_id="1", post_title="", post_published="2026-01-01",
                post_edited=None, artist_id="fanbox_1")
    base.update(kw)
    return ExternalLink(**base)


check("empty config -> no filter (shows everything)", make_link_filter({}) is None)

flt = make_link_filter({"allowed_domains": ["mega.nz", "drive.google.com"],
                        "reviewed_artists": ["fanbox_9"],
                        "reviewed_before": "2026-02-10"})
check("allowed domain passes", flt(L()))
check("non-whitelisted domain dropped",
      not flt(L(url="https://example.com/a", domain="example.com")))
check("reviewed artist's old link hidden",
      not flt(L(artist_id="fanbox_9", post_published="2026-01-01")))
check("reviewed artist's post after cutoff still shows",
      flt(L(artist_id="fanbox_9", post_published="2026-03-01")))
check("an edit after the cutoff resurfaces an old post",
      flt(L(artist_id="fanbox_9", post_published="2026-01-01", post_edited="2026-03-01")))

flt2 = make_link_filter({"reviewed_artists": ["fanbox_9"]})
check("no cutoff -> reviewed artist fully hidden",
      not flt2(L(artist_id="fanbox_9", post_published="2026-03-01")))
check("no domain list -> any domain passes",
      flt2(L(url="https://example.com/a", domain="example.com")))

# 6. links-all grouping: keys parsed in input order, deduped; '/' nests levels.
from src.cli.commands import _group_keys, _emit_grouped
from src.cli.registry import CommandError

check("single key", _group_keys("artist") == ["artist"])
check("two keys keep input order", _group_keys("artist/domain") == ["artist", "domain"])
check("reversed order is honored", _group_keys("domain/artist") == ["domain", "artist"])
check("aliases resolve (d/a)", _group_keys("d/a") == ["domain", "artist"])
check("'type' is an alias for domain", _group_keys("type") == ["domain"])
check("duplicates collapse", _group_keys("artist/artist") == ["artist"])
check("blank -> no grouping", _group_keys("") == [])
try:
    _group_keys("artist/bogus")
    check("unknown key raises", False)
except CommandError:
    check("unknown key raises", True)

# 7. _emit_grouped nests by the given order and counts correctly.
import io as _io
links = [
    L(artist_id="fanbox_1", domain="mega.nz", url="https://mega.nz/1", post_id="p1"),
    L(artist_id="fanbox_1", domain="mega.nz", url="https://mega.nz/2", post_id="p2"),
    L(artist_id="fanbox_1", domain="drive.google.com", url="https://drive.google.com/3", post_id="p3"),
    L(artist_id="fanbox_2", domain="mega.nz", url="https://mega.nz/4", post_id="p4"),
]
names = {"fanbox_1": "Alice [fanbox_1]", "fanbox_2": "Bob [fanbox_2]"}

buf = _io.StringIO(); _real = sys.stdout; sys.stdout = buf
shown = _emit_grouped(links, ["artist", "domain"], details=False, names=names, cap=100)
sys.stdout = _real
out = buf.getvalue()
check("emit returns links printed", shown == 4)
check("larger artist bucket (Alice, 3) printed before Bob (1)",
      out.index("Alice [fanbox_1]  (3)") < out.index("Bob [fanbox_2]  (1)"))
check("domain nested under artist with count", "mega.nz  (2)" in out and "drive.google.com  (1)" in out)
check("leaf shows post id + url", "[p1] https://mega.nz/1" in out)

long_title = "A very long post title that must not be truncated in details mode"
det_links = [L(domain="mega.nz", url="https://mega.nz/1", post_id="p1",
               post_title=long_title, post_published="2026-03-04T12:00:00")]
buf = _io.StringIO(); sys.stdout = buf
_emit_grouped(det_links, ["domain"], details=True, names={}, cap=100)
sys.stdout = _real
det = buf.getvalue()
check("details prints the url", "https://mega.nz/1" in det)
check("details prints full untruncated title", long_title in det)
check("details prints post id and date", "[p1]" in det and "2026-03-04" in det)

buf = _io.StringIO(); sys.stdout = buf
shown = _emit_grouped(links, ["domain"], details=False, names={}, cap=2)
sys.stdout = _real
check("cap limits printed leaf links", shown == 2)

print("\n" + ("ALL PASS" if not fails else f"FAILURES: {fails}"))
sys.exit(1 if fails else 0)
