# Refactor prompt — pawchive-downloader

You are refactoring the `pawchive-downloader` codebase — a Python scraper that
tracks creators on Pawchive, caches their post lists, and downloads files
concurrently. Treat this as a BEHAVIOR-PRESERVING refactor: improve structure,
clarity, and conciseness without changing what the program does or weakening any
guarantee below. The constraints in this document are non-negotiable and override
any instinct to simplify.

## 1. Data integrity outranks everything, including speed
Completeness of the scraped data is the top priority; performance is always
secondary. Never trade any risk of losing a post or a file for speed. Every
existing safeguard against silent loss must survive the refactor intact.

## 2. Never silently lose or truncate data
- All reads/writes of cache and state JSON are atomic (temp file + os.replace).
  A corrupt or truncated file MUST raise, never be read as empty `[]` — an empty
  read makes an artist look brand-new and its whole back-catalogue is skipped.
- A non-list API response is retried, never coerced to `[]` (which looks like the
  end of a creator's post list).
- A plain sync never shrinks a post's known file set; a shorter/empty response is
  logged and ignored.
- Cached posts absent from a fetch are kept (transient gap) and the shortfall is
  logged.

## 3. The retry policy is deliberate, not a bug
- API list/profile requests retry on EVERY failure (connection, timeout, 4xx,
  5xx) FOREVER (`max_retries=0`). Losing a list response truncates a creator, so
  unbounded retry is an intentional 100%-download guarantee. Keep it.
- File downloads are BOUNDED (`download_max_retries`): Pawchive serves 503/404 for
  files it has not materialized, and an unbounded wait there stalls the queue. A
  give-up is recorded as a failed file; the post stays undone and the next run
  retries it — data converges to 100% across runs.
- A 404 is PERMANENT (retried a few times to rule out a bad edge node, then
  raised): a creator removed upstream must not hang the unbounded retry and block
  every creator behind it.
- Cancellation / Ctrl+C always breaks out of any retry loop.

## 4. Preserve these correctness invariants exactly
Each fixed a real, proven data-loss or corruption bug. Do not regress any of them.
- PATH DEDUP: Pawchive repeats the cover as both `file` and `attachments[0]` on
  ~5% of posts. File entries are de-duplicated by content-hash path (download
  once), and re-download is triggered only by a LARGER distinct-path count.
- FILENAME DERIVATION: an attachment with only a `path` and no `name` derives its
  filename from the content-hash path basename (unique, correct extension), never
  a constant.
- UNIQUE TARGET PATHS: resolved filenames are de-duplicated before download so two
  files never target the same path.
- ATOMIC FILE WRITES: each download goes to a uniquely-named `.part`, is
  size-verified against Content-Length (a short read is treated as truncated and
  retried, never renamed into place), then placed with os.replace. A download that
  cannot be size-verified never overwrites an existing file.
- PAGING: the post list is re-paged every sync; paging never stops on a merely
  short page, only on an EMPTY page confirmed by a second request. Posts are
  sorted by `published` desc, so a backfilled old post lands deep in the list —
  only a full page-through finds it.
- `profile.updated` IS UNRELIABLE (a bulk-import batch timestamp; posts are
  inserted after it) and must not be trusted to skip a sync unless
  `trust_updated_timestamp` is explicitly set.
- PROGRESSIVE METADATA: Pawchive can serve a post before `published`/`title` are
  filled in and set them on a later scrape — adopt a present value, never
  overwrite a known value with null/empty.
- CANCELLATION: the per-artist cancel flag is the single source of truth and is
  cleared only by the run itself (no timeout may un-cancel a straggler). A single
  `cancel` must never globally abort HTTP (that would truncate other running
  artists); only `cancel-all` may abort in-flight requests, and only after all
  targets are flagged.
- `.part` SWEEP runs once per artist before any post thread starts, so it can
  never delete another thread's in-flight temp file.

## 5. Definition of "missing"
Re-download applies only to an artist whose download was actually triggered and
where a code defect may have skipped a post/file. An artist that was never scraped
is NOT "missing" — never mass-fetch it.

## 6. Environment vs config separation
Machine-specific paths/endpoints/tools come from the environment (`PAWCHIVE_*` and
standard proxy vars); behavior (templates, concurrency, retries, filters, timers)
lives in `data/config.json`. Precedence: environment > config.json > defaults. An
env override is never written back into the shared config file.

## 7. Package layering
`common/` imports nothing else in the project; `core/` never imports from
`services/` or `cli/`. Dependency arrows point inward only. Preserve this.

## Code-quality requirements
- As concise, idiomatic, and readable as possible while remaining correct.
- Comments only where necessary and kept minimal; a comment explains WHY (the
  non-obvious constraint), never restates WHAT the code does.
- No dead code, unused fields, or speculative abstraction.

## Completeness requirements — implement the task FULLY
- No stubs, no `TODO`/`pass`/"left as an exercise", no partial functions, no "you
  can add X later". Every function you touch is finished and working.
- Behavior-preserving: every existing command, flag, and output stays working and
  equivalent. Do not drop features to simplify.
- If you change any interface, update every caller in the same change.
- ACCEPTANCE GATE: `python -m pytest tests/` must stay green. The regression
  suite in `tests/` covers the invariants above (cancellation, retry policy,
  dedup, paging flap, corrupt-cache refusal, atomic writes / `.part` sweep,
  env/config precedence, URL parsing).
  `tests/test_regressions.py` runs each `*_test.py`/`audit_cache.py` script in a
  subprocess; the scripts are standalone programs, deliberately not collected by
  pytest directly (see `pytest.ini`). If you move code they cover, adapt the
  scripts to the new locations — never delete the assertions.
- If any constraint above conflicts with the task, STOP and flag it rather than
  silently weakening the guarantee.
- State every assumption you make explicitly.

## The task

Refactor the codebase for clarity, elegance, and a markedly better command-line
experience. The scraping / caching / download engine and every guarantee in
sections 1–7 stay behavior-preserving. The freedom to change, reshape, and *add*
is in three areas: code form, project structure, and the CLI/command layer.
Enriching or reorganizing commands and improving the terminal UI is IN scope and
does not violate "behavior-preserving" — dropping or weakening existing
functionality does. Deliver all six of the following, each fully:

### 1. Cleaner, more elegant code
- Tighten every module: remove indirection that earns nothing, collapse
  near-duplicate helpers, prefer small pure functions with clear names.
- Consistent style throughout — naming, argument order, return shapes, error
  handling. No module should read as if written by a different hand.
- Zero dead code, unused fields, or speculative abstraction. If something is not
  reachable or not used, delete it.

### 2. Leaner comments
- Keep only comments that state a non-obvious WHY — an invariant, a race, a
  Pawchive quirk, a reason a safe-looking simplification is unsafe. The invariants
  in section 4 are exactly the kind that must keep a short comment.
- Delete every comment that restates what the code plainly does, every commented-
  out block, and every redundant docstring. A one-line docstring is enough for
  most functions; some need none.

### 3. Clearer, tidier project structure
- Preserve the inward-only layering (`common` → `core` → `services`/`cli`).
- Make each package's responsibility obvious from its layout; group files by role,
  give them intention-revealing names, and split any module that has grown into
  two concerns. Keep public entry points (`main.py`, package `__init__`) minimal
  and readable.
- Update every import and the README's layout section to match. No orphaned files.

### 4. Smoother CLI interaction
- The interactive shell should feel effortless: forgiving command parsing,
  helpful and specific error messages (never a bare stack trace to the user),
  consistent confirmation prompts for destructive actions, and clean Ctrl+C
  handling that never corrupts state mid-write.
- Keep and polish the existing niceties: Tab completion (command + artist
  id/name/alias), persistent history, and graceful degradation to plain input()
  when prompt_toolkit is absent or stdin is piped.
- Artist selection should be fast to drive by id/name with completion, without
  dumping a full table first (that behavior was intentionally removed — keep it
  removed; `list` is how you browse).

### 5. Clearer command input box and download-progress display
- The prompt line and live download progress must not fight each other. Background
  download output currently interleaves with the input line; fix that — e.g. a
  stable input line at the bottom (prompt_toolkit patch_stdout / bottom toolbar)
  with progress rendered in its own region above it, or an equivalent clean
  separation.
- Progress should be legible at a glance: per-artist and per-file state, counts of
  done / pending / failed, and current throughput where cheap to compute. It must
  degrade gracefully in a non-TTY / piped context (fall back to periodic line
  logging, no ANSI garbage).
- Respect the existing `notify` config switch and the notifier's
  `on_download_progress` hook as the single progress channel; do not add a second,
  divergent progress path.

### 6. A richer, more rigorous command system
- Make the command set complete and symmetric: where a single-target command
  exists, provide its `-all` / batch form when it makes sense, and vice versa;
  fill obvious gaps. Keep every current command working (same name or an
  explicit, documented alias).
- Make it rigorous: one consistent inline-param syntax (`command:key=value,...`),
  per-command validation with clear messages for missing/unknown/invalid params,
  and a single dispatch path — no ad-hoc parsing scattered across handlers.
- `help` must be accurate and self-updating: it should reflect the real command
  map and its groups, not a hand-maintained list that can drift.
- Keep the plugin/hot-reload command mechanism working if it survives the
  restructure; if you change how commands are registered, the reload path and the
  help output must both still be correct.

### Acceptance
- `python -m pytest tests/` stays green. If you move code the suite covers, adapt
  the nine regression scripts to the new locations — never delete an assertion.
- Every existing command, flag, config field, and env var still works and produces
  equivalent results for the engine paths; CLI presentation may look better but
  must expose the same capabilities plus the additions above.
- Manually exercise the shell end-to-end (add, list, sync, download, tasks,
  cancel, cancel-all, config) and confirm the input line and progress display
  behave as specified in a real terminal.
