# pawchive-downloader

A downloader for [Pawchive](https://pawchive.st). Tracks creators, caches their
posts, and downloads files concurrently with incremental updates and scheduling.

It is a sibling of `kemono-downloader-v2` and reuses the same creator/post ids,
so `artists.json` entries can be carried over — only the `url` and file host
differ. See `src/api.py` for the API differences.

## Installation

```bash
pip install -r requirements.txt
```

Only dependency is `requests`. Optionally copy the example configs:

```bash
cp data/config.example.json data/config.json     # optional; sane defaults otherwise
cp data/artists.example.json data/artists.json   # optional
```

## Migrating from kemono-downloader-v2

Pawchive reuses kemono's creator/post ids, so existing data carries over. From a
side-by-side checkout of both projects:

```bash
python migrate_from_kemono.py            # defaults to ../kemono-downloader-v2
python migrate_from_kemono.py <path>     # or point at a kemono-v2 checkout
```

It copies (never moves) your artists, the `data/artists/` folder tree (urls
rewritten to pawchive.st), the posts cache (per-post `done` state preserved, so
finished posts aren't re-downloaded) and compatible config fields. Afterwards
run `check-all` to resume where kemono left off.

## Usage

```bash
python main.py
```

Type `help` for the full command list. Basic workflow:

```text
> add                  # Add a creator by URL (kemono or pawchive URL both work)
> list                 # List tracked creators and their progress
> check                # Queue a download for one creator
> check-all            # Queue downloads for all active creators
> tasks                # Watch queued / running / recent tasks
```

Commands take inline params as `command:key=value,key=value`, e.g.:

```text
> list:sort_by=recent,service=fanbox
> list-all
> history:limit=25
```

### Downloading by date

```text
> check-from           # Posts published after a date
> check-until          # Posts published up to a date
> check-range          # Posts within a date range
```

### Files & layout

Downloads are written as:

```
downloads/ / {artist_folder} / {post_folder} / {file}
```

templated by `artist_folder_template`, `post_folder_template` and
`file_template` (global, overridable per-artist via `config-artist`). Post text
is saved to `content.txt` when `save_content` is enabled.

### Scheduling

Set `global_timer` in `config.json` (or a per-artist `timer`) to auto-check on a
`daily` / `weekly` / `monthly` cadence while the program is running.

### Interactive prompt

When `prompt_toolkit` is installed the `> ` prompt gains **Tab command
completion** (substring/fuzzy) and **persistent history** (↑/↓, seeded from
`data/history.json`); artist selection prompts complete on number/id/name/alias.
Without it — or when stdin is piped — everything degrades to plain `input()`.

### Plugins (hot reload)

`src/cli.py`'s `COMMAND_MAP` and `plugins/format_plugin.py` are re-read from disk
on every use, so you can edit command handlers or path-formatting logic and see
the change on the next command — no restart. `plugins/format_plugin.py` ships as
no-op hooks with commented examples (e.g. trim a specific creator's titles);
delete the file to disable plugins entirely.

## How it works

- **API** (`src/api.py`) — talks to `https://pawchive.st/api/v1`. Post lists come
  from `/{service}/user/{id}` (already including each post's files & content),
  and full files download from `https://file.pawchive.st/data{path}?f={name}`.
  Since the profile has no post count, the list is paged until a short page and
  change detection diffs the profile `updated` timestamp.
- **Cache** (`src/cache.py`) — one `{id}_posts.json` + `{id}_profile.json` per
  creator, tracking per-post `done` state so re-runs only fetch what's new.
- **Downloader** (`src/downloader.py`) — concurrent across artists × posts ×
  files, advancing each artist's `last_date` over the contiguous run of
  completed posts.
- **Scheduler** (`src/scheduler.py`) — bounded worker pool fed by manual and
  timer-triggered tasks.
