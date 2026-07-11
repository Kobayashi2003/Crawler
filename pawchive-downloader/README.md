# pawchive-downloader

Downloads creator posts and attachments from [Pawchive](https://pawchive.pw) — an
interactive shell that tracks creators, caches their post lists, and fetches new
files incrementally. Downloads run concurrently across creators, posts and files,
with optional scheduling.

## Install

```bash
pip install -r requirements.txt
```

`requests` is the only hard dependency; `prompt_toolkit` adds Tab-completion and
persistent history to the prompt and degrades gracefully if absent.

## Usage

```bash
python main.py
```

Type `help` for the full command list. The common ones:

| Command | Description |
|---|---|
| `add` | Track a creator by URL |
| `list` | Active creators and their progress |
| `sync` / `sync-all` | Refresh cached post lists (no files) |
| `download` | Download one creator's pending posts |
| `download-all` | Queue every active creator |
| `download-pending` | Queue only creators that still have posts to get |
| `tasks` | Show the download queue |
| `cancel` / `cancel-all` | Cancel one / every queued & running download |
| `config` / `config-artist` | Edit global / per-creator settings |

Some commands take inline params as `command:key=value` — `list:sort_by=recent,service=fanbox`,
`sync:deep=true` (also catch edits), `links:match=drive\.google`, `reset:after_date=2025-01-01`,
`history:limit=25`. Date-range downloads (`download-after` / `-before` / `-between`)
prompt for their dates.

### Example

```text
> add                    # paste a creator URL
> download-all           # queue everything active
> tasks                  # watch progress
```

## Configuration

Files land in `{download_dir}/{artist_folder}/{post_folder}/{file}`, templated by
`artist_folder_template`, `post_folder_template` and `file_template` — global in
`data/config.json`, overridable per creator via `config-artist`. Set `global_timer`
(or a per-creator `timer`) for `daily`/`weekly`/`monthly` auto-checks while the
program runs.

Behaviour (templates, concurrency, retries, filters) lives in `data/config.json`;
machine-specific paths and endpoints come from the environment. Copy `.env.example`
to `.env` — real environment variables win over it.

```
precedence:  environment  >  data/config.json  >  built-in defaults
```

| Variable | Purpose |
|---|---|
| `PAWCHIVE_DOWNLOAD_DIR` | where files are written |
| `PAWCHIVE_DATA_DIR` | where `config.json` lives — env only, it locates that file |
| `PAWCHIVE_CACHE_DIR` / `PAWCHIVE_LOGS_DIR` | runtime locations |
| `PAWCHIVE_API_BASE` / `PAWCHIVE_FILE_BASE` | endpoints (Pawchive has moved `.st` → `.pw`) |
| `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` | standard names, read by `requests` |

## Notes

Completeness is prioritised over speed. Files are written to a unique temp file,
size-checked, then placed with an atomic `os.replace`; anything that fails is
recorded so the post stays pending and the next run retries it. Re-running is
always safe — finished posts are never re-fetched.
