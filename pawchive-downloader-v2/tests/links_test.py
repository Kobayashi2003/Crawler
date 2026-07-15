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

print("\n" + ("ALL PASS" if not fails else f"FAILURES: {fails}"))
sys.exit(1 if fails else 0)
