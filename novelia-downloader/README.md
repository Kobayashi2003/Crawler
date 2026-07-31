# novelia-downloader

Downloader for [n.novelia.cc](https://n.novelia.cc) (轻小说机翻机器人). Search a keyword, pick works
from a checkbox list, and get **Japanese-only EPUBs laid out for vertical reading** — built from
the site's bilingual files and checked against a Japanese reference build.

## Two catalogues

The site keeps two separate libraries, and one search covers both:

| | 文库小说 (library) | 网络小说 (web) |
|---|---|---|
| What it is | Published light-novel volumes | Serialised web novels |
| One work is | A set of volume files | A stream of chapters |
| Source | The publisher's own EPUB | Built from scraped chapters |
| Typography | The publisher's typesetting | Plain generated markup |
| Needs a token to search | No | Yes |

Results are shown together, tagged `[文库]` / `[网络]`, with the published volumes listed first
and preselected — for reading in Japanese those are almost always what you want.

```
Found 2 work(s): 1 文库 (published), 1 网络 (web).
❯ [x] [文库] 強くてニューサーガ            11 巻 · アルファポリス      强者的新传说
  [ ] [网络] 強くてニューサーガ            连载中 · JP 86 · ZH …      强者的新传说
```

Restrict with `-k wenku` or `-k web`.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Search both catalogues (web results need a token, see below)
python main.py "強くてニューサーガ"

# Straight to a known work — no token needed either way
python main.py --id wenku/688da4c4c923db0b7aa9943e     # library
python main.py --id alphapolis/159124863-713069479     # web

# Only some volumes
python main.py --id wenku/688da4c4c923db0b7aa9943e --volumes 1-3
```

```
  強くてニューサーガ: 11 volume(s)
  got     [阿部正行]強くてニューサーガ1 [jp-zh].epub (5462 KB)
  convert [阿部正行]強くてニューサーガ1 [ja].epub
          22 chapter(s): kept 3598 Japanese paragraph(s) + 0 blank line(s),
          dropped 3598 Chinese paragraph(s), left 143 original-markup paragraph(s) alone;
          vertical-rl restored from the publisher's own stylesheet
          verify: OK — identical to the publisher's uploaded original across 22 chapter(s)
```

Library volumes land in `downloads/<query>/<work title>/`, one file per volume.

### Options

| Option | Description | Default |
|---|---|---|
| `query` | Search keyword; prompted for when omitted | — |
| `--id ID` | Take a work directly: `wenku/<id>` or `<provider>/<novelId>`. Repeatable, no token | — |
| `-k, --kind` | Catalogue to search: `both`, `wenku`, `web` | `both` |
| `--volumes` | For library works: `1,3,5-8` | all |
| `-o, --output_dir` | Output directory | `downloads` |
| `-m, --mode` | Source build: `jp`, `zh`, `zh-jp`, `jp-zh` | `jp-zh` |
| `-p, --pages` | Search pages to read (20 works each) | `1` |
| `--providers` | Web sources to search | all six |
| `--translations` | Translation engines, best first | `sakura,gpt,youdao` |
| `--translations_mode` | `priority` (one) or `parallel` (all) | `priority` |
| `--file_type` | `epub` or `txt` — web novels only; library volumes are always epub | `epub` |
| `--no-convert` | Keep the bilingual file as downloaded | off |
| `--no-vertical` | Japanese-only but horizontal layout | off |
| `--keep_original` | Also keep the bilingual download | off |
| `--no-verify` | Skip the check against the Japanese reference | off |
| `-t, --token` | Login token (also `token.txt` / `NOVELIA_TOKEN`) | — |
| `-w, --workers` | Concurrent downloads — across works, and across the volumes of one library work | `3` |
| `-y, --yes` | Take every result, skip the checkbox list | off |
| `--dry-run` | List what would be downloaded and stop | off |

## The token

Only the **web-novel search** is authenticated. Everything else — library search, metadata, and
every file download — is open, so `--id` and `-k wenku` work with no token at all. Without one you
still get library results, with a note explaining what was skipped.

To enable web search, log in on the site, then in the browser console:

```js
JSON.parse(localStorage.auth).profile.token
```

Save that string to `token.txt` next to `main.py` (it is gitignored), or set `NOVELIA_TOKEN`.
Tokens expire; when search starts failing, repeat the step.

## The builds, and why conversion exists

| Mode | Contents | Library | Web |
|---|---|---|---|
| `zh` | Chinese only | yes | yes |
| `jp` | Japanese only | **no — HTTP 400** | yes |
| `zh-jp` | Bilingual, Chinese first (中与日) | yes | yes |
| `jp-zh` | Bilingual, Japanese first (日与中) | yes | yes |

A library volume has **no Japanese-only build**, so the bilingual file is the only route to the
Japanese text of a published volume. That is exactly what the converter is for.

### How the languages are told apart

The site marks up its two catalogues differently, and both are handled:

* **Web novels** tag every Japanese paragraph `lang="ja"` and leave Chinese ones as bare `<p>`.
* **Library volumes** reuse the publisher's EPUB, so its own markup survives — the Japanese
  paragraphs keep their original attributes and carry *no* `lang`.

The one marker present in both is the dimming style the site adds to the Japanese side, so that
is what identifies Japanese. Everything else follows: a bare `<p>` with text is the inserted
translation and is dropped; a bare *empty* `<p>` is a spacer and is kept; a paragraph with its own
attributes belongs to the original book and is left untouched. On a library volume the Japanese
and Chinese counts come out exactly 1:1 (3598 : 3598 for volume 1), which is what confirms the rule.

Headings carry no marker at all and are emitted **Japanese-first in both** bilingual modes, so
they are matched by kana — kana never appear in Chinese.

### Verification

Every conversion is checked paragraph by paragraph against a Japanese reference:

* **library** — the publisher's uploaded original at `/files-wenku/{id}/{volumeId}`
* **web** — the site's own `mode=jp` build

`verify: OK` means the result is *identical in content* to that reference, so the conversion
provably lost nothing. `--no-verify` skips the extra download.

On a mismatch nothing is thrown away and nothing is passed off as finished: the bilingual source
is kept so the problem can be investigated, and the output is renamed to `… [UNVERIFIED].epub`.

## Vertical layout

The site's bilingual builds actively **break** vertical reading: they strip
`page-progression-direction` from the spine, set `primary-writing-mode` to `horizontal-lr`, and
empty every stylesheet to zero bytes.

* **Library volumes** — the publisher's stylesheets are copied back from the uploaded original, so
  you get the real typesetting rather than an approximation, plus the spine and Kindle metadata
  restored to `vertical-rl`.
* **Web novels** — there is no original to restore, so a stylesheet is generated:
  `writing-mode: vertical-rl` (with `-epub-` and `-webkit-` prefixes), a mincho stack,
  `line-break: strict`, and `text-combine-upright` for runs of digits.

`--no-vertical` turns all of this off.

## Layout

```
main.py              CLI: search -> select -> download -> convert -> verify
src/config.py        defaults, config.json, NOVELIA_* overrides
src/models.py        Novel, Volume, ConversionReport
src/session.py       requests session, bearer auth, retries
src/api.py           both catalogues' endpoints
src/convert.py       bilingual -> Japanese-only, vertical layout, verification
src/selector.py      checkbox list (prompt_toolkit) + text fallback
src/naming.py        filesystem-safe names
```

Importable: `from src.convert import convert_epub, verify_against_jp`.
