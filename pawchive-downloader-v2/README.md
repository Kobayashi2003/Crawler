# pawchive-downloader

Downloads creator posts and attachments from [Pawchive](https://pawchive.pw) — an
interactive shell that tracks creators, caches their post lists, and fetches new
files incrementally. Downloads run concurrently across creators, posts and files,
with optional scheduling.

## Install

```bash
pip install -r requirements.txt
```

`requests` is the only hard dependency; `prompt_toolkit` adds Tab-completion,
persistent history, a live status bar and a stable input line, and degrades
gracefully if absent.

## Usage

```bash
python main.py
```

Type `help` for the full command list (generated from the live command registry,
so it is always current). The common ones:

| Command | Description |
|---|---|
| `add` | Track a creator by URL |
| `list` | Active creators and their progress |
| `info` | One creator's details, overrides and progress |
| `sync` / `sync-all` | Refresh cached post lists (no files) |
| `download` | Download one creator's pending posts |
| `download-all` | Queue every active creator |
| `download-pending` / `download-failed` | Queue only creators with pending posts / failed files |
| `tasks` | Show the download queue |
| `cancel` / `cancel-all` | Cancel one / every queued & running download |
| `config` / `config-artist` | Edit global / per-creator settings |

Commands take inline params as `command:key=value,key=value` —
`list:sort_by=recent,service=fanbox`, `sync:artist=hane,deep=true`,
`links:match=drive\.google`, `reset:after_date=2025-01-01`, `history:limit=25`.
A single bare value goes to the first parameter (`help sync`, `download hane`),
and a unique prefix resolves (`hist` → `history`). Parameters are validated per
command; a wrong key or value gets a specific message, never a stack trace.

Commands that act on one creator accept `artist=` inline (id, name, alias, or a
unique fragment) or prompt with Tab completion — browsing happens via `list`,
selection never dumps a table first.

While downloads run in the background, the prompt line stays fixed at the bottom
with a once-a-second status bar (running/queued tasks, file count, throughput);
progress lines print above it without disturbing input. With the `notify` config
switch off, per-file progress is silent. In a piped/non-TTY session everything
falls back to plain line output with no ANSI codes.

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

## Layout

```
main.py           entry point: object graph, signal handling, shell start
src/common/       generic helpers — logging, naming, backoff, hot reload,
                  atomic JSON I/O, download progress (imports nothing else)
src/core/         models + the fetch -> cache -> download pipeline
src/services/     optional features built on core: migrate, validate, links
src/cli/          registry (declarative commands), commands (hot-reloaded
                  handlers), shell (loop + error policy), prompt (completion,
                  history, status bar)
src/plugins/      user-editable, hot-reloaded plugin files
tests/            regression suite — `python -m pytest tests/`
```

Dependency arrows point inward only: `common` imports nothing else in the
project; `core` never imports from `services` or `cli`.

## Notes

Completeness is prioritised over speed. Files are written to a unique temp file,
size-checked, then placed with an atomic `os.replace`; anything that fails is
recorded so the post stays pending and the next run retries it. Re-running is
always safe — finished posts are never re-fetched.
