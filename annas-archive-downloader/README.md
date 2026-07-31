# annas-archive-downloader

Semi-automatic series downloader for [Anna's Archive](https://annas-archive.gl). You give it a
keyword; it searches, works out which volume each hit belongs to, keeps the best file for each
volume, shows them as a checkbox list, and downloads the ones you tick.

"Best" means, in order:

1. **Format** — `epub` before everything else (`epub, azw3, mobi, fb2, djvu, cbz, cbr, pdf`).
2. **Size** — the larger file wins.
3. **Date** — the newer one wins.

The order and the format list are both configurable (`--rank`, `--format_priority`).

## Install

```bash
pip install -r requirements.txt
```

`selenium` is only needed for the `browser` download backend; everything else works without a
browser.

## Usage

```bash
python main.py "Sword Art Online"
```

```
Searching https://annas-archive.gl for 'Sword Art Online'…
Found 50 files.
21 volume(s) identified, 0 file(s) without a volume number.

Sword Art Online — best file per volume (rank: format, size, date; formats: epub, azw3, mobi…)
↑/↓ move · space toggle · a all · n none · i invert · enter download · q cancel

❯ [x] Vol.1   Sword Art Online Alternative Clover's Regret, Vol. 1   EPUB · 23.5MB · 2024  (+4 other: EPUB, MOBI)
  [x] Vol.3   Sword Art Online Progressive 3 [TNC]                   EPUB · 15.1MB · 2017  (+2 other: PDF)
  [x] Vol.4   Sword Art Online - Volume 04 - Fairy Dance             EPUB · 16.4MB · 2017
  …
```

Files land in `downloads/<keyword>/<volume> <title>.<ext>`. An entry that already exists is
skipped, so re-running after an interruption resumes the set.

Without a tty (or without `prompt_toolkit`) the same list is printed numbered and you type a
selection expression instead: `1,3,5-8`, `all`, `none`, `-4` to drop one, blank to accept.

### Options

| Option | Description | Default |
|---|---|---|
| `query` | Search keyword; prompted for when omitted | — |
| `-o, --output_dir` | Output directory | `downloads` |
| `-p, --pages` | Search pages to read, 50 hits each | `1` |
| `-l, --language` | Language filter, e.g. `en`, `zh`, `ja` | all |
| `-e, --extension` | Restrict the search itself to one format | all |
| `--mirror` | Anna's Archive mirror | `https://annas-archive.gl` |
| `--sort` | Server-side ordering (`newest`, `largest`, `newest_added`, …) | relevance |
| `--rank` | Ranking keys, best first: `format`, `size`, `date`, `fast` | `format,size,date` |
| `--format_priority` | Format preference order | `epub,azw3,mobi,fb2,djvu,cbz,cbr,pdf` |
| `--volume_from` | Read the volume from `auto`/`title`/`publisher`/`filename` | `auto` |
| `--volume_regex` | Custom volume pattern, one capturing group | — |
| `--loose` | Keep hits that miss a query word | off |
| `--partial` | Also take the site's "partial matches" (they ignore `--language`/`--extension`) | off |
| `--precise_date` | Rank on the real "date open sourced" (one request per hit) | off |
| `--backend` | `auto`, `member`, `libgen`, `browser` | `auto` |
| `-k, --secret_key` | Anna's Archive membership key | — |
| `-b, --browser` | `chrome`, `edge`, `firefox`, `auto` | `auto` |
| `--headless` | Run the browser backend headless | off |
| `-w, --workers` | Concurrent downloads | `3` |
| `--proxy` | HTTP(S) proxy URL | env |
| `--config` | Config file | `config.json` |
| `-y, --yes` | Take every volume, skip the checkbox list | off |
| `--dry-run` | Print the picks and stop | off |

### Examples

```bash
# Two pages of results, Japanese only, prefer the newest file over the largest
python main.py "ソードアート・オンライン アリシゼーション" -p 2 -l ja --rank format,date,size

# Members: one request per file, no waitlist
python main.py "Sword Art Online" -k YOUR_SECRET_KEY

# See what it would pick without downloading anything
python main.py "Frieren" --dry-run -y
```

## Download backends

`auto` tries them in this order and stops at the first that yields a link.

| Backend | Needs | Notes |
|---|---|---|
| `member` | A membership key (`-k`, `ANNAS_SECRET_KEY`, or `config.json`) | Uses `/dyn/api/fast_download.json`. One request, no waitlist. |
| `libgen` | Nothing | Follows the Libgen mirror the record's own page links to. Covers most of the library; records that only exist on Z-Library are not reachable this way. |
| `browser` | `selenium` + Chrome/Edge/Firefox | Drives the site's slow-download page: clears DDoS-Guard, waits out the countdown, reads the final link. Slow, and it is the only route for Z-Library-only records. |

A file the chosen backend cannot resolve is reported and the run continues with the rest.

### Cookies

`/search` and `/md5/` answer a plain client, but `/dyn/…` and `/slow_download/…` sit behind
DDoS-Guard. Exporting those cookies from a logged-in browser into `cookies.json` lets the plain
client through as well. Both shapes are accepted:

```json
{ "ddg8_": "…", "cf_clearance": "…" }
```

```json
[ { "name": "ddg8_", "value": "…", "domain": "annas-archive.gl", "path": "/" } ]
```

## Partial matches

A search page holds the real results first, then — behind a "Show N partial matches" toggle,
sometimes inside an HTML comment — the hits that *failed* the language/format/content filters.
Those are ignored by default and reported as a count, because merging them silently undoes
`--language`:

```
Found 5 files.
Ignored 45 partial match(es) that fail the filters (--partial includes them).
```

Pass `--partial` when you would rather have a wrong-language edition than nothing.

## Configuration

Anything in the table above can also live in `config.json` (copy `config.example.json`) or come
from the environment as `ANNAS_<OPTION>` — `ANNAS_SECRET_KEY`, `ANNAS_MIRROR`, `ANNAS_WORKERS`,
and so on. Precedence is command line > environment > `config.json` > defaults.

## How volumes are detected

Volume numbers are written a dozen ways, and the three places to read them from — title,
publisher/edition line, original filename — disagree often enough that order matters:

- An **explicit** marker (`Vol. 3`, `第3巻`, `v03`, `#07`, `Book 2`) is authoritative and is looked
  for in the title first, then the edition line, then the filename.
- A **bare** number (`Sword Art Online 12: …`, `ソードアート・オンライン16 …`) is only a guess, so the
  structured edition line is consulted before the title, and filenames are skipped entirely —
  their paths are full of years and batch numbers.

Anything with no readable volume still shows up in the list, under `?`, unticked by default.
When the guess is wrong for your series, `--volume_from` narrows the source and `--volume_regex`
replaces the whole thing:

```bash
python main.py "Berserk" --volume_regex 'Deluxe\s+Edition\s+(\d+)'
```

## Layout

```
main.py              CLI: parse args, run search -> group -> select -> download
src/config.py        defaults, config.json, ANNAS_* overrides
src/models.py        Record, VolumeGroup
src/session.py       requests session, cookies, retries
src/search.py        search URLs, result parsing, detail-page lookups
src/volumes.py       volume detection, relevance filter, ranking, grouping
src/selector.py      checkbox list (prompt_toolkit) + text fallback
src/downloader.py    member / libgen / browser backends, concurrent saving
src/naming.py        filesystem-safe names
```

Importable: `from src.search import search`, `from src.volumes import group_by_volume`.
