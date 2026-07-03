from datetime import datetime
from typing import List, Optional

from .api import API
from .cache import Cache
from .downloader import Downloader
from .models import Artist
from .prompt import prompt_artist
from .scheduler import Scheduler
from .storage import Storage


class CLIContext:
    """Bundle of services passed to every command handler."""

    def __init__(self, storage: Storage, cache: Cache, api: API,
                 downloader: Downloader, scheduler: Scheduler):
        self.storage = storage
        self.cache = cache
        self.api = api
        self.downloader = downloader
        self.scheduler = scheduler
        self._last_artist: Optional[str] = None


# ============================================================================
# Helpers
# ============================================================================

def _c(text, code):
    return f"\033[{code}m{text}\033[0m"


def _status(artist: Artist) -> str:
    if artist.completed:
        return "DONE"
    if artist.ignore:
        return "IGNORE"
    return "Active"


# ---- Shared artist-table rendering (used by `list` and artist selection) ----

_TABLE_HEADER = f"{'#':>3}  {'STATUS':<6}  {'DONE/TOTAL':>11}  {'FAIL':>4}  NAME"


def _artist_row(ctx: CLIContext, index: int, artist: Artist, color: bool = True) -> str:
    """Format one aligned artist row. `done/total` is combined before padding so
    the column stays aligned regardless of digit count."""
    s = ctx.cache.stats(artist.id)
    progress = f"{s['done']}/{s['total']}"
    line = (f"{index:>3}  {_status(artist):<6}  {progress:>11}  "
            f"{s['failed']:>4}  {artist.display_name()} [{artist.id}]")
    if not color:
        return line
    if artist.completed:
        return _c(line, 92)   # green
    if artist.ignore:
        return _c(line, 90)   # gray
    if s['total'] == 0 or s['pending'] or s['failed']:
        return _c(line, 91)   # red: nothing cached, or pending/failed work
    return line


def print_artist_table(ctx: CLIContext, artists: List[Artist], color: bool = True):
    """Print the shared artist table with header. Rows are 1-indexed."""
    print("\n" + _TABLE_HEADER)
    print("-" * 70)
    for i, a in enumerate(artists, 1):
        print(_artist_row(ctx, i, a, color=color))


def get_artists(ctx: CLIContext, only_active=False, service="", sort_by="name") -> List[Artist]:
    artists = ctx.storage.get_artists()
    if only_active:
        artists = [a for a in artists if not a.ignore and not a.completed]
    if service:
        artists = [a for a in artists if a.service.lower() == service.lower()]
    if sort_by == "name":
        artists.sort(key=lambda a: a.display_name().lower())
    elif sort_by == "recent":
        artists.sort(key=lambda a: a.last_date or "", reverse=True)
    elif sort_by == "posts":
        artists.sort(key=lambda a: ctx.cache.stats(a.id)['total'], reverse=True)
    elif sort_by == "service":
        artists.sort(key=lambda a: (a.service, a.display_name().lower()))
    return artists


def select_artist(ctx: CLIContext) -> Optional[Artist]:
    """Prompt the user to pick an artist by number, id, name or alias."""
    artists = get_artists(ctx)
    if not artists:
        print("No artists. Use 'add' first.")
        return None
    print_artist_table(ctx, artists)
    try:
        raw = prompt_artist("\nSelect artist (number/id/name, Tab to complete): ", artists)
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled")
        return None
    if not raw:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(artists):
        artist = artists[int(raw) - 1]
    else:
        low = raw.lower()
        artist = next((a for a in artists if a.id.lower() == low
                       or a.name.lower() == low or a.alias.lower() == low), None)
        if not artist:
            matches = [a for a in artists if low in a.display_name().lower() or low in a.id.lower()]
            if len(matches) == 1:
                artist = matches[0]
            elif len(matches) > 1:
                print("Ambiguous; be more specific.")
                return None
    if not artist:
        print("Not found.")
        return None
    ctx._last_artist = artist.id
    return artist


# ============================================================================
# Commands
# ============================================================================

def cmd_help(ctx: CLIContext):
    print("""
Pawchive Downloader — commands  (params: command:key=value,key=value)

  Artists
    add                       Add an artist by URL
    remove                    Remove an artist
    list | ls                 List active artists   (list:sort_by=recent,service=fanbox)
    list-all | la             List all artists incl. ignored/completed
    ignore / unignore         Toggle ignore on an artist
    complete / uncomplete     Mark an artist done / active
    unignore-all / uncomplete-all

  Download
    check                     Download updates for one artist
    check-all                 Queue updates for all active artists
    check-from                Download posts published after a date
    check-until               Download posts published up to a date
    check-range               Download posts within a date range
    check-undone              Re-download undone posts for one artist
    update-cache              Refresh post list for one artist (no download)
    update-all                Refresh post list for all active artists

  State / maintenance
    reset / reset-all         Mark posts undone (optionally after a date)
    dedupe / dedupe-all       Remove duplicate cached posts
    tasks                     Show queued / running / recent tasks
    cancel-all                Cancel all running & queued downloads

  Config
    config-global             Edit global settings
    config-artist             Edit per-artist overrides

  Misc
    history [limit]           Recent commands
    help / clear / exit
""")


def cmd_add(ctx: CLIContext):
    url = input("Artist URL (kemono or pawchive): ").strip()
    if not url:
        print("URL required.")
        return
    parts = url.rstrip('/').split('/')
    if len(parts) < 5:
        print("Invalid URL. Expected .../{service}/user/{id}")
        return
    service, user_id = parts[-3], parts[-1]
    artist_id = f"{service}_{user_id}"
    if ctx.storage.get_artist(artist_id):
        print(f"Artist {artist_id} already exists.")
        return

    name = None
    try:
        print("Fetching profile...")
        profile = ctx.api.get_profile(service, user_id)
        name = profile.get('name')
        if name:
            print(f"Name: {name}")
    except Exception as e:
        print(f"Could not fetch profile: {e}")
    if not name:
        name = input("Artist name: ").strip() or user_id

    alias = input("Alias (optional): ").strip()
    last_date = input("Skip posts before (YYYY-MM-DDTHH:MM:SS, optional): ").strip()
    if last_date:
        try:
            datetime.fromisoformat(last_date)
        except ValueError:
            print("Invalid date format.")
            return

    artist = Artist(
        id=artist_id, service=service, user_id=user_id, name=name,
        url=f"https://pawchive.st/{service}/user/{user_id}",
        alias=alias, last_date=last_date or None,
    )
    ctx.storage.save_artist(artist)
    ctx._last_artist = artist_id
    print(f"Added: {artist.display_name()} [{artist_id}]")


def cmd_remove(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    if input(f"Remove {artist.display_name()}? (yes/no): ").strip().lower() != "yes":
        print("Cancelled.")
        return
    ctx.storage.remove_artist(artist.id)
    print(f"Removed {artist.display_name()}.")


def cmd_list(ctx: CLIContext, sort_by="name", service="", all="false"):
    show_all = str(all).lower() in ("true", "1", "yes")
    artists = get_artists(ctx, only_active=not show_all, service=service, sort_by=sort_by)
    if not artists:
        print("No artists.")
        return
    print_artist_table(ctx, artists)
    print(f"\nTotal: {len(artists)}")


def cmd_list_all(ctx: CLIContext, sort_by="name", service=""):
    cmd_list(ctx, sort_by=sort_by, service=service, all="true")


def _toggle(ctx: CLIContext, field: str, value: bool, label: str):
    artist = select_artist(ctx)
    if not artist:
        return
    setattr(artist, field, value)
    ctx.storage.save_artist(artist)
    print(f"{artist.display_name()} -> {label}")


def cmd_ignore(ctx):        _toggle(ctx, 'ignore', True, 'ignored')
def cmd_unignore(ctx):      _toggle(ctx, 'ignore', False, 'active')
def cmd_complete(ctx):      _toggle(ctx, 'completed', True, 'completed')
def cmd_uncomplete(ctx):    _toggle(ctx, 'completed', False, 'active')


def _bulk_flag(ctx: CLIContext, field: str, value: bool, label: str):
    count = 0
    for a in ctx.storage.get_artists():
        if getattr(a, field) != value:
            setattr(a, field, value)
            ctx.storage.save_artist(a)
            count += 1
    print(f"{count} artists -> {label}")


def cmd_unignore_all(ctx):    _bulk_flag(ctx, 'ignore', False, 'active')
def cmd_uncomplete_all(ctx):  _bulk_flag(ctx, 'completed', False, 'active')


# ---------------- Download ----------------

def cmd_check(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    if ctx.scheduler.queue_manual(artist.id):
        print(f"Queued {artist.display_name()}. Use 'tasks' to monitor.")
    else:
        print("Already queued or running.")


def cmd_check_all(ctx: CLIContext):
    ids = [a.id for a in get_artists(ctx, only_active=True)]
    added = ctx.scheduler.queue_batch(ids)
    print(f"Queued {added}/{len(ids)} artists.")


def cmd_check_from(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    frm = input("From date (YYYY-MM-DD or ISO): ").strip()
    if not frm:
        return
    if ctx.scheduler.queue_manual(artist.id, from_date=frm):
        print(f"Queued {artist.display_name()} from {frm}.")


def cmd_check_until(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    until = input("Until date (YYYY-MM-DD or ISO): ").strip()
    if not until:
        return
    if ctx.scheduler.queue_manual(artist.id, until_date=until):
        print(f"Queued {artist.display_name()} until {until}.")


def cmd_check_range(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    frm = input("From date: ").strip()
    until = input("Until date: ").strip()
    if ctx.scheduler.queue_manual(artist.id, from_date=frm or None, until_date=until or None):
        print(f"Queued {artist.display_name()} [{frm or '*'} .. {until or '*'}].")


def cmd_check_undone(ctx: CLIContext):
    # A normal download already targets undone + previously-failed posts; this
    # is a convenience alias that reports how many are pending before queueing.
    artist = select_artist(ctx)
    if not artist:
        return
    pending = len(ctx.cache.get_undone(artist.id))
    if ctx.scheduler.queue_manual(artist.id):
        print(f"Queued {artist.display_name()} ({pending} undone posts).")
    else:
        print("Already queued or running.")


def cmd_update_cache(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    print("Refreshing cache...")
    changed = ctx.downloader.update_posts(artist)
    s = ctx.cache.stats(artist.id)
    print(f"{'Updated' if changed else 'No change'}. {s['done']}/{s['total']} done.")


def cmd_update_all(ctx: CLIContext):
    artists = get_artists(ctx, only_active=True)
    print(f"Refreshing {len(artists)} artists...")
    changed = 0
    for a in artists:
        try:
            if ctx.downloader.update_posts(a):
                changed += 1
                print(f"  updated {a.display_name()}")
        except Exception as e:
            print(f"  failed {a.display_name()}: {e}")
    print(f"Done. {changed} updated.")


# ---------------- Maintenance ----------------

def cmd_reset(ctx: CLIContext, after_date=""):
    artist = select_artist(ctx)
    if not artist:
        return
    n = ctx.cache.reset_after_date(artist.id, after_date or None)
    print(f"Reset {n} posts for {artist.display_name()}.")


def cmd_reset_all(ctx: CLIContext, after_date=""):
    if input("Reset posts for ALL artists? (yes/no): ").strip().lower() != "yes":
        return
    total = sum(ctx.cache.reset_after_date(a.id, after_date or None) for a in ctx.storage.get_artists())
    print(f"Reset {total} posts.")


def cmd_dedupe(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    print(f"Removed {ctx.cache.deduplicate(artist.id)} duplicates.")


def cmd_dedupe_all(ctx: CLIContext):
    total = sum(ctx.cache.deduplicate(a.id) for a in ctx.storage.get_artists())
    print(f"Removed {total} duplicates total.")


# ---------------- Tasks ----------------

def cmd_tasks(ctx: CLIContext):
    st = ctx.scheduler.status()
    print(f"\nQueued: {st['queued']}  Running: {st['running']}  Completed: {st['completed']}")
    active = ctx.scheduler.list_active()
    if active:
        print("\nRunning:")
        for t in active:
            print(f"  [{t.task_type}] {t.artist_id}")
    queued = ctx.scheduler.list_queued()
    if queued:
        print("\nQueued:")
        for t in queued[:20]:
            print(f"  [{t.task_type}] {t.artist_id}")
    recent = ctx.scheduler.completed[-10:]
    if recent:
        print("\nRecent:")
        for t in reversed(recent):
            err = f" ({t.error})" if t.error else ""
            print(f"  [{t.status}] {t.artist_id}{err}")


def cmd_cancel_all(ctx: CLIContext):
    n = ctx.scheduler.cancel_all()
    print(f"Cancelled. {n} were running.")


# ---------------- Config ----------------

def cmd_config_global(ctx: CLIContext):
    config = ctx.storage.load_config()
    editable = [
        'download_dir', 'date_format', 'artist_folder_template', 'post_folder_template',
        'file_template', 'save_content', 'save_empty_posts', 'rename_images_only',
        'max_concurrent_artists', 'max_concurrent_posts', 'max_concurrent_files',
        'proxy', 'retry_delay', 'request_timeout',
    ]
    print("\nGlobal config (blank = keep):")
    changed = False
    for key in editable:
        current = getattr(config, key)
        val = input(f"  {key} [{current}]: ").strip()
        if val == "":
            continue
        if isinstance(current, bool):
            val = val.lower() in ("true", "1", "yes")
        elif isinstance(current, int):
            try:
                val = int(val)
            except ValueError:
                print(f"    skipped (not an int)")
                continue
        setattr(config, key, val)
        changed = True
    if changed:
        ctx.storage.save_config(config)
        print("Saved. Restart to apply concurrency/proxy changes.")
    else:
        print("No changes.")


def cmd_config_artist(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    keys = ['artist_folder_template', 'post_folder_template', 'file_template',
            'date_format', 'save_content', 'download_dir']
    print(f"\nOverrides for {artist.display_name()} (blank = keep, '-' = clear):")
    for key in keys:
        current = artist.config.get(key, "(inherit)")
        val = input(f"  {key} [{current}]: ").strip()
        if val == "":
            continue
        if val == "-":
            artist.config.pop(key, None)
        elif val.lower() in ("true", "false"):
            artist.config[key] = val.lower() == "true"
        else:
            artist.config[key] = val
    ctx.storage.save_artist(artist)
    print("Saved.")


def cmd_history(ctx: CLIContext, limit="10"):
    try:
        n = int(limit)
    except ValueError:
        n = 10
    for r in ctx.storage.get_history(n):
        mark = "ok " if r.success else "ERR"
        extra = f" {r.params}" if r.params else ""
        print(f"  [{mark}] {r.timestamp[:19]} {r.command}{extra}")


def cmd_clear(ctx: CLIContext):
    print("\033[2J\033[H", end="")


def cmd_exit(ctx: CLIContext):
    raise KeyboardInterrupt


COMMAND_MAP = {
    'help': cmd_help, 'clear': cmd_clear, 'exit': cmd_exit, 'quit': cmd_exit,
    'history': cmd_history, 'tasks': cmd_tasks, 'cancel-all': cmd_cancel_all,

    'add': cmd_add, 'remove': cmd_remove,
    'list': cmd_list, 'ls': cmd_list, 'list-all': cmd_list_all, 'la': cmd_list_all,

    'ignore': cmd_ignore, 'unignore': cmd_unignore, 'unignore-all': cmd_unignore_all,
    'complete': cmd_complete, 'uncomplete': cmd_uncomplete, 'uncomplete-all': cmd_uncomplete_all,

    'check': cmd_check, 'check-all': cmd_check_all,
    'check-from': cmd_check_from, 'check-until': cmd_check_until, 'check-range': cmd_check_range,
    'check-undone': cmd_check_undone,
    'update-cache': cmd_update_cache, 'update-all': cmd_update_all,

    'reset': cmd_reset, 'reset-all': cmd_reset_all,
    'dedupe': cmd_dedupe, 'dedupe-all': cmd_dedupe_all,

    'config-global': cmd_config_global, 'config-artist': cmd_config_artist,
}
