from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from ..common import env
from ..core.api import API
from ..core.cache import Cache
from ..core.downloader import Downloader
from ..core.files import get_config_value
from ..core.models import Artist, MigrationConfig
from ..core.scheduler import Scheduler
from ..core.storage import Storage
from ..services.external_links import ExternalLinksDownloader, ExternalLinksExtractor
from ..services.migrator import Migrator
from ..services.validator import Validator
from .prompt import prompt_artist


class CLIContext:
    """Bundle of services passed to every command handler."""

    def __init__(self, storage: Storage, cache: Cache, api: API,
                 downloader: Downloader, scheduler: Scheduler,
                 migrator: Migrator, validator: Validator,
                 links_extractor: ExternalLinksExtractor,
                 links_downloader: ExternalLinksDownloader):
        self.storage = storage
        self.cache = cache
        self.api = api
        self.downloader = downloader
        self.scheduler = scheduler
        self.migrator = migrator
        self.validator = validator
        self.links_extractor = links_extractor
        self.links_downloader = links_downloader
        self._last_artist: Optional[str] = None


# ============================================================================
# Helpers
# ============================================================================

def _c(text, code):
    return f"\033[{code}m{text}\033[0m"


def _flag(value, default: bool = False) -> bool:
    """Parse an inline ``:key=value`` param as a boolean."""
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "y"):
        return True
    if text in ("false", "0", "no", "n"):
        return False
    return default


def _confirm(question: str) -> bool:
    """Ask for an explicit `yes` before doing something destructive."""
    if input(f"{question} (yes/no): ").strip().lower() == "yes":
        return True
    print("Cancelled.")
    return False


def _status(artist: Artist, corrupt: bool = False) -> str:
    if corrupt:
        return "BROKEN"
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
    corrupt = s.get('corrupt')
    progress = "?/?" if corrupt else f"{s['done']}/{s['total']}"
    line = (f"{index:>3}  {_status(artist, corrupt):<6}  {progress:>11}  "
            f"{s['failed']:>4}  {artist.display_name()} [{artist.id}]")
    if not color:
        return line
    if corrupt:
        return _c(line, 91)   # red: cache unreadable, state unknown
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
Pawchive Downloader   (add params inline: command:key=value,key=value)

  CREATORS — manage the tracked list
    add                          Track a new creator (by URL)
    remove                       Stop tracking a creator
    ignore / unignore            Hide / unhide a creator (skips downloads)
    unignore-all                 Unhide every creator
    ignore-inactive[:months=6]   Ignore creators idle for N months
    complete / uncomplete        Mark a creator finished / active again
    uncomplete-all               Reactivate every finished creator

  BROWSE — list creators   (:sort_by=name|recent|posts|service, :service=fanbox)
    list | ls                    Active creators
    list-all | la                Everything, incl. ignored & finished
    list-ignored                 Ignored only
    list-completed               Finished only
    list-pending                 Active creators with posts still to get
    list-failed                  Creators with failed files

  DOWNLOAD — fetch and save files
    download                     Download one creator's pending posts
    download-all                 Queue all active creators
    download-pending             Queue only creators that have pending posts
    download-after               Only posts published after a date
    download-before              Only posts published up to a date
    download-between             Only posts within a date range

  SYNC — refresh the cached post list (no files)   (:deep=true also catches edits)
    sync                         Refresh one creator
    sync-all                     Refresh all active creators

  INSPECT
    undone                       Show one creator's remaining posts
    links[:match=regex]          External URLs in one creator's posts
    links-all                    External URLs across all creators
    download-gdrive              Download found Google Drive links (needs gdown)

  MAINTAIN — fix the cache & files
    reset / reset-all            Mark posts undone (optionally :after_date=)
    reset-conflicts / -conflicts-all   Undo posts whose output paths collide
    dedupe / dedupe-all          Remove duplicate cached posts
    validate / validate-all      Report colliding output paths
    clean-folders[:dry=false]    Quarantine orphan download folders
    relayout-posts / relayout-files    Move files to match new templates

  TASKS & CONFIG
    tasks                        Show the download queue
    cancel                       Cancel one queued/running download
    cancel-all                   Cancel every queued & running download
    config / config-artist       Edit global / per-creator settings
    config-conflicts             Manage muted path conflicts

  SESSION
    history[:limit=10]   test   help   clear   exit
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
        url=f"https://pawchive.pw/{service}/user/{user_id}",
        alias=alias, last_date=last_date or None,
    )
    ctx.storage.save_artist(artist)
    ctx._last_artist = artist_id
    print(f"Added: {artist.display_name()} [{artist_id}]")


def cmd_remove(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    if not _confirm(f"Remove {artist.display_name()}?"):
        return
    ctx.storage.remove_artist(artist.id)
    print(f"Removed {artist.display_name()}.")


def _is_active(a: Artist) -> bool:
    return not a.ignore and not a.completed


def _has_work(ctx: CLIContext, a: Artist) -> bool:
    """True if the artist has posts left to fetch/download (or nothing cached)."""
    s = ctx.cache.stats(a.id)
    return s['total'] == 0 or s['pending'] > 0 or s['failed'] > 0


def _show_list(ctx: CLIContext, predicate=None, sort_by="name", service="", label="artists"):
    artists = get_artists(ctx, service=service, sort_by=sort_by)
    if predicate:
        artists = [a for a in artists if predicate(a)]
    if not artists:
        print(f"No {label}.")
        return
    print_artist_table(ctx, artists)
    print(f"\nTotal: {len(artists)} {label}")


def cmd_list(ctx: CLIContext, sort_by="name", service=""):
    _show_list(ctx, _is_active, sort_by, service, "active artists")


def cmd_list_all(ctx: CLIContext, sort_by="name", service=""):
    _show_list(ctx, None, sort_by, service, "artists")


def cmd_list_ignored(ctx: CLIContext, sort_by="name", service=""):
    _show_list(ctx, lambda a: a.ignore, sort_by, service, "ignored artists")


def cmd_list_completed(ctx: CLIContext, sort_by="name", service=""):
    _show_list(ctx, lambda a: a.completed, sort_by, service, "completed artists")


def cmd_list_pending(ctx: CLIContext, sort_by="name", service=""):
    _show_list(ctx, lambda a: _is_active(a) and _has_work(ctx, a),
               sort_by, service, "artists with pending work")


def cmd_list_failed(ctx: CLIContext, sort_by="name", service=""):
    _show_list(ctx, lambda a: ctx.cache.stats(a.id)['failed'] > 0,
               sort_by, service, "artists with failed files")


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


# ---------------- Download (fetch + save files) ----------------

def cmd_download(ctx: CLIContext):
    """Download a creator's pending posts (optionally within a date window)."""
    artist = select_artist(ctx)
    if not artist:
        return
    if ctx.scheduler.queue_manual(artist.id):
        pending = len(ctx.cache.get_undone(artist.id))
        print(f"Queued {artist.display_name()} ({pending} pending). Use 'tasks' to monitor.")
    else:
        print("Already queued or running.")


def cmd_download_all(ctx: CLIContext):
    ids = [a.id for a in get_artists(ctx, only_active=True)]
    added = ctx.scheduler.queue_batch(ids)
    print(f"Queued {added}/{len(ids)} active creators.")


def cmd_download_pending(ctx: CLIContext):
    """Queue only active creators that still have undone posts."""
    ids = [a.id for a in get_artists(ctx, only_active=True) if ctx.cache.get_undone(a.id)]
    added = ctx.scheduler.queue_batch(ids)
    print(f"Queued {added} creators with pending posts.")


def cmd_download_after(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    date = input("Published after (YYYY-MM-DD or ISO): ").strip()
    if date and ctx.scheduler.queue_manual(artist.id, from_date=date):
        print(f"Queued {artist.display_name()} for posts after {date}.")


def cmd_download_before(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    date = input("Published up to (YYYY-MM-DD or ISO): ").strip()
    if date and ctx.scheduler.queue_manual(artist.id, until_date=date):
        print(f"Queued {artist.display_name()} for posts up to {date}.")


def cmd_download_between(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    after = input("Published after: ").strip()
    before = input("Published up to: ").strip()
    if ctx.scheduler.queue_manual(artist.id, from_date=after or None, until_date=before or None):
        print(f"Queued {artist.display_name()} [{after or '*'} .. {before or '*'}].")


# ---------------- Sync (refresh cached post list, no file download) ----------------

def cmd_sync(ctx: CLIContext, deep="false"):
    """Refresh one creator's cached post list. deep=true also re-flags edited posts."""
    artist = select_artist(ctx)
    if not artist:
        return
    is_deep = _flag(deep)
    print("Syncing" + (" (deep: detecting edits)" if is_deep else "") + "...")
    new, edited = ctx.downloader.update_posts(artist, detect_edits=is_deep)
    s = ctx.cache.stats(artist.id)
    note = f", {edited} edited re-flagged" if is_deep else ""
    print(f"{'Updated' if new or edited else 'No change'}. {s['done']}/{s['total']} done, {new} new{note}.")


def cmd_sync_all(ctx: CLIContext, deep="false"):
    """Refresh all active creators. deep=true also re-flags edited posts."""
    is_deep = _flag(deep)
    artists = get_artists(ctx, only_active=True)
    print(f"Syncing {len(artists)} creators" + (" (deep)" if is_deep else "") + "...")
    total_new = total_edited = 0
    for a in artists:
        try:
            new, edited = ctx.downloader.update_posts(a, detect_edits=is_deep)
            total_new += new
            total_edited += edited
        except Exception as e:
            print(f"  failed {a.display_name()}: {e}")
    note = f", {total_edited} edited re-flagged" if is_deep else ""
    print(f"Done. {total_new} new posts{note}.")


# ---------------- Inspect one creator's posts ----------------

def cmd_undone(ctx: CLIContext):
    """Show the selected creator's remaining (undone) posts."""
    artist = select_artist(ctx)
    if not artist:
        return
    undone = ctx.cache.get_undone(artist.id)
    if not undone:
        print(f"{artist.display_name()} is fully downloaded.")
        return
    print(f"\n{len(undone)} undone posts for {artist.display_name()}:")
    for p in sorted(undone, key=lambda p: p.published or ''):
        flag = f" [{len(p.failed_files)} failed]" if p.failed_files else ""
        print(f"  [{(p.published or '')[:10]}] [{p.id}] {p.title[:60]}{flag}")


# ---------------- Ignore inactive ----------------

def cmd_ignore_inactive(ctx: CLIContext, months="6"):
    try:
        cutoff = (datetime.now() - timedelta(days=int(months) * 30)).isoformat()
    except ValueError:
        print("months must be a number.")
        return
    stale = [a for a in get_artists(ctx, only_active=True)
             if (a.last_date or "") and a.last_date < cutoff]
    if not stale:
        print(f"No active artists inactive for {months}+ months.")
        return
    print(f"\n{len(stale)} artists inactive since before {cutoff[:10]}:")
    for a in stale:
        print(f"  {a.display_name()} (last {a.last_date[:10]})")
    if not _confirm("\nIgnore all of these?"):
        return
    for a in stale:
        a.ignore = True
        ctx.storage.save_artist(a)
    print(f"Ignored {len(stale)} artists.")


# ---------------- Validation ----------------

def _print_conflicts(conflicts):
    if not conflicts:
        print("No path conflicts. ✓")
        return
    print(f"\n{len(conflicts)} conflicting output paths:")
    for path, ids in conflicts[:50]:
        print(f"  {path}")
        print(f"      <- {', '.join(ids)}")
    if len(conflicts) > 50:
        print(f"  ... and {len(conflicts) - 50} more")


def cmd_validate(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    _print_conflicts(ctx.validator.find_conflicts([artist]))


def cmd_validate_all(ctx: CLIContext):
    print("Checking all artists for output-path collisions...")
    _print_conflicts(ctx.validator.find_conflicts(ctx.storage.get_artists()))


def cmd_config_conflicts(ctx: CLIContext):
    data = ctx.validator.load_ignores()
    ignored = data.get('ignored_paths', [])
    print(f"\nMuted conflict paths: {len(ignored)}")
    for p in ignored[:50]:
        print(f"  {p}")
    print("\nActions: [c]lear all, [a]dd current conflicts, [Enter] cancel")
    choice = input("> ").strip().lower()
    if choice == 'c':
        ctx.validator.clear_ignores()
        print("Cleared.")
    elif choice == 'a':
        conflicts = ctx.validator.find_conflicts(ctx.storage.get_artists())
        ctx.validator.ignore_paths([p for p, _ in conflicts])
        print(f"Muted {len(conflicts)} current conflicts.")


def cmd_reset_conflicts(ctx: CLIContext):
    artist = select_artist(ctx)
    if not artist:
        return
    n = ctx.validator.reset_conflicts(artist)
    print(f"Reset {n} conflicting posts to undone.")


def cmd_reset_conflicts_all(ctx: CLIContext):
    total = sum(ctx.validator.reset_conflicts(a) for a in ctx.storage.get_artists())
    print(f"Reset {total} conflicting posts across all artists.")


def cmd_clean_folders(ctx: CLIContext, quarantine="_invalid", dry="true"):
    artist = select_artist(ctx)
    if not artist:
        return
    _clean_one(ctx, artist, quarantine, dry)


def cmd_clean_folders_all(ctx: CLIContext, quarantine="_invalid", dry="true"):
    for a in get_artists(ctx, only_active=True):
        _clean_one(ctx, a, quarantine, dry)


def _clean_one(ctx: CLIContext, artist, quarantine, dry):
    is_dry = _flag(dry, default=True)
    moves = ctx.validator.clean_post_folders(artist, quarantine=quarantine, dry=is_dry)
    if not moves:
        return
    verb = "Would move" if is_dry else "Moved"
    print(f"{artist.display_name()}: {verb} {len(moves)} orphan folder(s) -> {quarantine}/")
    for src, _dst in moves[:10]:
        print(f"    {Path(src).name}")
    if is_dry:
        print("    (dry run; re-run with :dry=false to apply)")


# ---------------- Migration ----------------

def _migration_config(ctx: CLIContext, artist, prompt_label):
    """Prompt for the templates of one side of a migration, defaulting to the
    artist's effective (config-merged) templates."""
    cv = lambda k: get_config_value(artist, ctx.storage.load_config(), k)
    print(f"\n{prompt_label} templates (blank = current effective value):")
    af = input(f"  artist_folder_template [{cv('artist_folder_template')}]: ").strip() or cv('artist_folder_template')
    pf = input(f"  post_folder_template [{cv('post_folder_template')}]: ").strip() or cv('post_folder_template')
    ff = input(f"  file_template [{cv('file_template')}]: ").strip() or cv('file_template')
    return MigrationConfig(
        download_dir=cv('download_dir'),
        artist_folder_template=af, post_folder_template=pf, file_template=ff,
        date_format=cv('date_format'), rename_images_only=cv('rename_images_only'),
        image_extensions=ctx.storage.load_config().image_extensions,
    )


def _run_migration(ctx: CLIContext, kind):
    artist = select_artist(ctx)
    if not artist:
        return
    old = _migration_config(ctx, artist, "OLD (where files are now)")
    new = _migration_config(ctx, artist, "NEW (where they should go)")
    plan = (ctx.migrator.plan_posts if kind == "post" else ctx.migrator.plan_files)(artist, old, new)
    print(f"\nPlan: {plan.success_count} to move, {len(plan.conflicts)} conflicts, "
          f"{len(plan.skipped)} skipped (of {plan.total_items}).")
    for src, dst, _id in plan.mappings[:10]:
        print(f"  {src}\n    -> {dst}")
    if plan.success_count > 10:
        print(f"  ... and {plan.success_count - 10} more")
    if not plan.mappings:
        return
    if not _confirm(f"\nApply {plan.success_count} moves?"):
        return
    result = ctx.migrator.execute(plan)
    print(f"Moved {result.success}/{result.total}. Failed: {len(result.failed)}.")


def cmd_relayout_posts(ctx: CLIContext):
    _run_migration(ctx, "post")


def cmd_relayout_files(ctx: CLIContext):
    _run_migration(ctx, "file")


# ---------------- External links ----------------

def cmd_links(ctx: CLIContext, match="", unique="true"):
    artist = select_artist(ctx)
    if not artist:
        return
    links = ctx.links_extractor.extract_from_artist(
        artist.id, match=match or None, unique=str(unique).lower() != "false")
    _print_links(ctx, links)


def cmd_links_all(ctx: CLIContext, match="", unique="true"):
    all_links = []
    for a in get_artists(ctx):
        all_links.extend(ctx.links_extractor.extract_from_artist(
            a.id, match=match or None, unique=str(unique).lower() != "false"))
    _print_links(ctx, all_links)


def _print_links(ctx: CLIContext, links):
    if not links:
        print("No links found.")
        return
    stats = ctx.links_extractor.statistics(links)
    print(f"\n{stats['total_links']} links across {stats['unique_posts']} posts "
          f"({stats['unique_domains']} domains). Top:")
    for domain, count in stats['top_domains'].items():
        print(f"  {count:>4}  {domain}")
    print()
    for link in links[:50]:
        print(f"  [{link.post_id}] {link.url}")
    if len(links) > 50:
        print(f"  ... and {len(links) - 50} more")


def cmd_download_gdrive(ctx: CLIContext, match=""):
    all_links = []
    for a in get_artists(ctx):
        all_links.extend(ctx.links_extractor.extract_from_artist(
            a.id, match=match or None,
            filter_func=lambda l: 'drive.google.com' in l.url or 'drive.google.com' in l.domain))
    urls = list(dict.fromkeys(l.url for l in all_links))
    if not urls:
        print("No Google Drive links found.")
        return
    print(f"Found {len(urls)} Google Drive links.")
    if not _confirm("Download them with gdown?"):
        return
    ctx.links_downloader.download_gdrive_links(urls)


def cmd_test(ctx: CLIContext):
    """Verify the plugin system is loading (calls plugins/test_plugin.py)."""
    from ..common.hotreload import dynamic_call
    try:
        result = dynamic_call('test_plugin', 'src/plugins/test_plugin.py', default=lambda: "(no plugin)")
        print(f"Plugin test result: {result() if callable(result) else result}")
    except Exception as e:
        print(f"Plugin test failed: {e}")


# ---------------- Maintenance ----------------

def cmd_reset(ctx: CLIContext, after_date=""):
    artist = select_artist(ctx)
    if not artist:
        return
    n = ctx.cache.reset_after_date(artist.id, after_date or None)
    print(f"Reset {n} posts for {artist.display_name()}.")


def cmd_reset_all(ctx: CLIContext, after_date=""):
    if not _confirm("Reset posts for ALL artists?"):
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


def _task_label(ctx: CLIContext, task) -> str:
    artist = ctx.storage.get_artist(task.artist_id)
    return artist.display_name() if artist else task.artist_id


def cmd_cancel(ctx: CLIContext):
    """Cancel a single queued or running download."""
    active = ctx.scheduler.list_active()
    queued = ctx.scheduler.list_queued()
    tasks = [('running', t) for t in active] + [('queued', t) for t in queued]
    if not tasks:
        print("Nothing to cancel.")
        return

    print("\nCancellable downloads:")
    for i, (state, t) in enumerate(tasks, 1):
        print(f"  {i}. [{state}] {_task_label(ctx, t)}")
    try:
        raw = input("\nCancel which (number/id, Enter to abort): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted")
        return
    if not raw:
        return

    if raw.isdigit() and 1 <= int(raw) <= len(tasks):
        artist_id = tasks[int(raw) - 1][1].artist_id
    else:
        low = raw.lower()
        match = next((t.artist_id for _, t in tasks
                      if t.artist_id.lower() == low or _task_label(ctx, t).lower() == low), None)
        if not match:
            print("No matching task.")
            return
        artist_id = match

    state = ctx.scheduler.cancel(artist_id)
    if state:
        print(f"Cancelled {artist_id} ({state}).")
    else:
        print(f"{artist_id} was no longer active.")


def cmd_cancel_all(ctx: CLIContext):
    n = ctx.scheduler.cancel_all()
    print(f"Cancelled all. {n} were running.")


# ---------------- Config ----------------

def cmd_config(ctx: CLIContext):
    config = ctx.storage.load_config()
    editable = [
        'download_dir', 'date_format', 'artist_folder_template', 'post_folder_template',
        'file_template', 'save_content', 'save_empty_posts', 'rename_images_only',
        'max_concurrent_artists', 'max_concurrent_posts', 'max_concurrent_files',
        'retry_delay', 'request_timeout', 'notify',
    ]
    print("\nGlobal config (blank = keep):")
    changed = False
    for key in editable:
        current = getattr(config, key)
        if env.get(key):
            # An env var wins, so editing here would be silently discarded.
            print(f"  {key} [{current}]  (from {env.PREFIX}{key.upper()}; not editable)")
            continue
        val = input(f"  {key} [{current}]: ").strip()
        if val == "":
            continue
        if isinstance(current, bool):
            val = val.lower() in ("true", "1", "yes")
        elif isinstance(current, int):
            try:
                val = int(val)
            except ValueError:
                print("    skipped (not an int)")
                continue
        setattr(config, key, val)
        changed = True
    if changed:
        ctx.storage.save_config(config)
        print("Saved. Restart to apply concurrency changes.")
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
    # Creators — manage
    'add': cmd_add, 'remove': cmd_remove,
    'ignore': cmd_ignore, 'unignore': cmd_unignore, 'unignore-all': cmd_unignore_all,
    'ignore-inactive': cmd_ignore_inactive,
    'complete': cmd_complete, 'uncomplete': cmd_uncomplete, 'uncomplete-all': cmd_uncomplete_all,

    # Browse — list creators
    'list': cmd_list, 'ls': cmd_list, 'list-all': cmd_list_all, 'la': cmd_list_all,
    'list-ignored': cmd_list_ignored, 'list-completed': cmd_list_completed,
    'list-pending': cmd_list_pending, 'list-failed': cmd_list_failed,

    # Download — fetch and save files
    'download': cmd_download, 'download-all': cmd_download_all,
    'download-pending': cmd_download_pending,
    'download-after': cmd_download_after, 'download-before': cmd_download_before,
    'download-between': cmd_download_between,

    # Sync — refresh cached post list
    'sync': cmd_sync, 'sync-all': cmd_sync_all,

    # Inspect
    'undone': cmd_undone,
    'links': cmd_links, 'links-all': cmd_links_all, 'download-gdrive': cmd_download_gdrive,

    # Maintain
    'reset': cmd_reset, 'reset-all': cmd_reset_all,
    'reset-conflicts': cmd_reset_conflicts, 'reset-conflicts-all': cmd_reset_conflicts_all,
    'dedupe': cmd_dedupe, 'dedupe-all': cmd_dedupe_all,
    'validate': cmd_validate, 'validate-all': cmd_validate_all,
    'clean-folders': cmd_clean_folders, 'clean-folders-all': cmd_clean_folders_all,
    'relayout-posts': cmd_relayout_posts, 'relayout-files': cmd_relayout_files,

    # Tasks & config
    'tasks': cmd_tasks, 'cancel': cmd_cancel, 'cancel-all': cmd_cancel_all,
    'config': cmd_config, 'config-artist': cmd_config_artist,
    'config-conflicts': cmd_config_conflicts,

    # Session
    'history': cmd_history, 'test': cmd_test,
    'help': cmd_help, 'clear': cmd_clear, 'exit': cmd_exit, 'quit': cmd_exit,
}
