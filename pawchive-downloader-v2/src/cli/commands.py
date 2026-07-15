"""Command handlers, registered declaratively so parsing, validation and
`help` share one source of truth (see registry.py).

This file is hot-reloaded by path: edit a handler, save, and the next command
uses it. COMMAND_MAP at the bottom is what the shell reads.
"""

import sys
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
from ..services.external_links import (ExternalLinksDownloader, ExternalLinksExtractor,
                                       make_link_filter)
from ..services.migrator import Migrator
from ..services.validator import Validator
from .prompt import ask, confirm, prompt_artist
from .registry import Command, CommandError, ExitShell, Param, build_map


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


_REGISTRY: List[Command] = []


def _cmd(name, group, summary, params=(), aliases=()):
    def register(fn):
        _REGISTRY.append(Command(name, fn, group, summary, tuple(params), tuple(aliases)))
        return fn
    return register


# Shared parameter specs.
_ARTIST = Param('artist', 'str', '', 'creator id, name or alias; prompted if omitted')
_LISTING = (Param('sort_by', 'str', 'name', 'name | recent | posts | service'),
            Param('service', 'str', '', 'only this service, e.g. fanbox'))
_DEEP = Param('deep', 'bool', False, 'also re-flag edited posts for re-download')


# ============================================================================
# Helpers
# ============================================================================

def _c(text, code):
    """ANSI color, only when stdout is a real terminal."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _status(artist: Artist, corrupt: bool = False) -> str:
    if corrupt:
        return "BROKEN"
    if artist.completed:
        return "DONE"
    if artist.ignore:
        return "IGNORE"
    return "Active"


_TABLE_HEADER = f"{'#':>3}  {'STATUS':<6}  {'DONE/TOTAL':>11}  {'FAIL':>4}  NAME"


def _artist_row(ctx: CLIContext, index: int, artist: Artist) -> str:
    """One aligned artist row. `done/total` is combined before padding so the
    column stays aligned regardless of digit count."""
    s = ctx.cache.stats(artist.id)
    corrupt = s.get('corrupt')
    progress = "?/?" if corrupt else f"{s['done']}/{s['total']}"
    line = (f"{index:>3}  {_status(artist, corrupt):<6}  {progress:>11}  "
            f"{s['failed']:>4}  {artist.display_name()} [{artist.id}]")
    if corrupt:
        return _c(line, 91)   # red: cache unreadable, state unknown
    if artist.completed:
        return _c(line, 92)   # green
    if artist.ignore:
        return _c(line, 90)   # gray
    if s['total'] == 0 or s['pending'] or s['failed']:
        return _c(line, 91)   # red: nothing cached, or pending/failed work
    return line


def print_artist_table(ctx: CLIContext, artists: List[Artist]):
    print("\n" + _TABLE_HEADER)
    print("-" * 70)
    for i, a in enumerate(artists, 1):
        print(_artist_row(ctx, i, a))


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


def _match_artist(artists: List[Artist], query: str) -> Optional[Artist]:
    """Exact index/id/name/alias first, then a unique substring of name or id."""
    if query.isdigit() and 1 <= int(query) <= len(artists):
        return artists[int(query) - 1]
    low = query.lower()
    exact = next((a for a in artists if a.id.lower() == low
                  or a.name.lower() == low or a.alias.lower() == low), None)
    if exact:
        return exact
    matches = [a for a in artists if low in a.display_name().lower() or low in a.id.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        sample = ', '.join(a.display_name() for a in matches[:5])
        raise CommandError(f"'{query}' is ambiguous: {sample}"
                           + (" ..." if len(matches) > 5 else ""))
    return None


def select_artist(ctx: CLIContext, query: str = "") -> Optional[Artist]:
    """Resolve an inline `artist=` value, or prompt with completion."""
    artists = get_artists(ctx)
    if not artists:
        print("No artists. Use 'add' first.")
        return None
    if not query:
        query = prompt_artist("Select artist (id/name, Tab to complete; 'list' to browse): ", artists)
        if not query:
            return None
    artist = _match_artist(artists, query)
    if not artist:
        raise CommandError(f"No artist matches '{query}'.")
    ctx._last_artist = artist.id
    return artist


def _is_active(a: Artist) -> bool:
    return not a.ignore and not a.completed


def _has_work(ctx: CLIContext, a: Artist) -> bool:
    """True if the artist has posts left to fetch/download (or nothing cached)."""
    s = ctx.cache.stats(a.id)
    return s['total'] == 0 or s['pending'] > 0 or s['failed'] > 0


# ============================================================================
# Creators
# ============================================================================

@_cmd('add', 'CREATORS', 'Track a new creator by URL')
def cmd_add(ctx: CLIContext):
    url = ask("Artist URL (kemono or pawchive): ")
    if url is None:
        return
    if not url:
        print("URL required.")
        return
    parts = url.rstrip('/').split('/')
    if len(parts) < 5:
        raise CommandError("Invalid URL. Expected .../{service}/user/{id}")
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
        name = ask("Artist name: ")
        if name is None:
            return
        name = name or user_id

    alias = ask("Alias (optional): ")
    if alias is None:
        return
    last_date = ask("Skip posts before (YYYY-MM-DDTHH:MM:SS, optional): ")
    if last_date is None:
        return
    if last_date:
        try:
            datetime.fromisoformat(last_date)
        except ValueError:
            raise CommandError("Invalid date format.")

    artist = Artist(
        id=artist_id, service=service, user_id=user_id, name=name,
        url=f"https://pawchive.pw/{service}/user/{user_id}",
        alias=alias, last_date=last_date or None,
    )
    ctx.storage.save_artist(artist)
    ctx._last_artist = artist_id
    print(f"Added: {artist.display_name()} [{artist_id}]")


@_cmd('remove', 'CREATORS', 'Stop tracking a creator', params=(_ARTIST,))
def cmd_remove(ctx: CLIContext, artist=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    if not confirm(f"Remove {artist.display_name()}?"):
        return
    ctx.storage.remove_artist(artist.id)
    print(f"Removed {artist.display_name()}.")


@_cmd('info', 'CREATORS', "Show one creator's details, overrides and progress",
      params=(_ARTIST,))
def cmd_info(ctx: CLIContext, artist=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    s = ctx.cache.stats(artist.id)
    print(f"\n{artist.display_name()} [{artist.id}]")
    print(f"  service    {artist.service}   user_id {artist.user_id}")
    print(f"  url        {artist.url or '-'}")
    if artist.alias:
        print(f"  alias      {artist.alias}   (name: {artist.name})")
    print(f"  status     {_status(artist, s.get('corrupt'))}")
    print(f"  last_date  {artist.last_date or '-'}")
    print(f"  timer      {artist.timer or '(global)'}")
    if s.get('corrupt'):
        print("  posts      cache unreadable (corrupt JSON)")
    else:
        print(f"  posts      {s['done']}/{s['total']} done, "
              f"{s['pending']} pending, {s['failed']} with failed files")
    if artist.config:
        print("  overrides  " + ", ".join(f"{k}={v}" for k, v in artist.config.items()))
    if artist.filter:
        print("  filter     " + ", ".join(f"{k}={v}" for k, v in artist.filter.items()))


def _toggle(ctx: CLIContext, query: str, field: str, value: bool, label: str):
    artist = select_artist(ctx, query)
    if not artist:
        return
    setattr(artist, field, value)
    ctx.storage.save_artist(artist)
    print(f"{artist.display_name()} -> {label}")


@_cmd('ignore', 'CREATORS', 'Hide a creator (skips downloads)', params=(_ARTIST,))
def cmd_ignore(ctx, artist=""):
    _toggle(ctx, artist, 'ignore', True, 'ignored')


@_cmd('unignore', 'CREATORS', 'Unhide a creator', params=(_ARTIST,))
def cmd_unignore(ctx, artist=""):
    _toggle(ctx, artist, 'ignore', False, 'active')


@_cmd('complete', 'CREATORS', 'Mark a creator finished', params=(_ARTIST,))
def cmd_complete(ctx, artist=""):
    _toggle(ctx, artist, 'completed', True, 'completed')


@_cmd('uncomplete', 'CREATORS', 'Mark a creator active again', params=(_ARTIST,))
def cmd_uncomplete(ctx, artist=""):
    _toggle(ctx, artist, 'completed', False, 'active')


def _bulk_flag(ctx: CLIContext, field: str, value: bool, label: str) -> int:
    count = 0
    for a in ctx.storage.get_artists():
        if getattr(a, field) != value:
            setattr(a, field, value)
            ctx.storage.save_artist(a)
            count += 1
    print(f"{count} artists -> {label}")
    return count


@_cmd('ignore-all', 'CREATORS', 'Ignore every creator')
def cmd_ignore_all(ctx):
    if confirm("Ignore ALL creators?"):
        _bulk_flag(ctx, 'ignore', True, 'ignored')


@_cmd('unignore-all', 'CREATORS', 'Unhide every creator')
def cmd_unignore_all(ctx):
    _bulk_flag(ctx, 'ignore', False, 'active')


@_cmd('complete-all', 'CREATORS', 'Mark every creator finished')
def cmd_complete_all(ctx):
    if confirm("Mark ALL creators as completed?"):
        _bulk_flag(ctx, 'completed', True, 'completed')


@_cmd('uncomplete-all', 'CREATORS', 'Reactivate every finished creator')
def cmd_uncomplete_all(ctx):
    _bulk_flag(ctx, 'completed', False, 'active')


@_cmd('ignore-inactive', 'CREATORS', 'Ignore creators idle for N months',
      params=(Param('months', 'int', 6, 'idle threshold in months'),))
def cmd_ignore_inactive(ctx: CLIContext, months=6):
    cutoff = (datetime.now() - timedelta(days=months * 30)).isoformat()
    stale = [a for a in get_artists(ctx, only_active=True)
             if (a.last_date or "") and a.last_date < cutoff]
    if not stale:
        print(f"No active artists inactive for {months}+ months.")
        return
    print(f"\n{len(stale)} artists inactive since before {cutoff[:10]}:")
    for a in stale:
        print(f"  {a.display_name()} (last {a.last_date[:10]})")
    if not confirm("\nIgnore all of these?"):
        return
    for a in stale:
        a.ignore = True
        ctx.storage.save_artist(a)
    print(f"Ignored {len(stale)} artists.")


# ============================================================================
# Browse
# ============================================================================

def _show_list(ctx: CLIContext, predicate, sort_by, service, label):
    artists = get_artists(ctx, service=service, sort_by=sort_by)
    if predicate:
        artists = [a for a in artists if predicate(a)]
    if not artists:
        print(f"No {label}.")
        return
    print_artist_table(ctx, artists)
    print(f"\nTotal: {len(artists)} {label}")


@_cmd('list', 'BROWSE', 'Active creators', params=_LISTING, aliases=('ls',))
def cmd_list(ctx, sort_by="name", service=""):
    _show_list(ctx, _is_active, sort_by, service, "active artists")


@_cmd('list-all', 'BROWSE', 'Everything, incl. ignored & finished',
      params=_LISTING, aliases=('la',))
def cmd_list_all(ctx, sort_by="name", service=""):
    _show_list(ctx, None, sort_by, service, "artists")


@_cmd('list-ignored', 'BROWSE', 'Ignored creators only', params=_LISTING)
def cmd_list_ignored(ctx, sort_by="name", service=""):
    _show_list(ctx, lambda a: a.ignore, sort_by, service, "ignored artists")


@_cmd('list-completed', 'BROWSE', 'Finished creators only', params=_LISTING)
def cmd_list_completed(ctx, sort_by="name", service=""):
    _show_list(ctx, lambda a: a.completed, sort_by, service, "completed artists")


@_cmd('list-pending', 'BROWSE', 'Active creators with posts still to get', params=_LISTING)
def cmd_list_pending(ctx, sort_by="name", service=""):
    _show_list(ctx, lambda a: _is_active(a) and _has_work(ctx, a),
               sort_by, service, "artists with pending work")


@_cmd('list-failed', 'BROWSE', 'Creators with failed files', params=_LISTING)
def cmd_list_failed(ctx, sort_by="name", service=""):
    _show_list(ctx, lambda a: ctx.cache.stats(a.id)['failed'] > 0,
               sort_by, service, "artists with failed files")


# ============================================================================
# Download
# ============================================================================

@_cmd('download', 'DOWNLOAD', "Download one creator's pending posts", params=(_ARTIST,))
def cmd_download(ctx: CLIContext, artist=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    if ctx.scheduler.queue_manual(artist.id):
        pending = len(ctx.cache.get_undone(artist.id))
        print(f"Queued {artist.display_name()} ({pending} pending). Use 'tasks' to monitor.")
    else:
        print("Already queued or running.")


@_cmd('download-all', 'DOWNLOAD', 'Queue all active creators')
def cmd_download_all(ctx: CLIContext):
    ids = [a.id for a in get_artists(ctx, only_active=True)]
    added = ctx.scheduler.queue_batch(ids)
    print(f"Queued {added}/{len(ids)} active creators.")


@_cmd('download-pending', 'DOWNLOAD', 'Queue only creators that have pending posts')
def cmd_download_pending(ctx: CLIContext):
    ids = [a.id for a in get_artists(ctx, only_active=True) if ctx.cache.get_undone(a.id)]
    added = ctx.scheduler.queue_batch(ids)
    print(f"Queued {added} creators with pending posts.")


@_cmd('download-failed', 'DOWNLOAD', 'Queue only creators that have failed files')
def cmd_download_failed(ctx: CLIContext):
    ids = [a.id for a in get_artists(ctx, only_active=True)
           if ctx.cache.stats(a.id)['failed'] > 0]
    added = ctx.scheduler.queue_batch(ids)
    print(f"Queued {added} creators with failed files.")


def _ask_date(value: str, label: str) -> Optional[str]:
    """Use the inline date if given, otherwise prompt; None means cancelled."""
    if value:
        return value
    raw = ask(f"{label} (YYYY-MM-DD or ISO): ")
    if raw is None or not raw:
        return None
    try:
        datetime.fromisoformat(raw)
    except ValueError:
        raise CommandError(f"Invalid date '{raw}'.")
    return raw


@_cmd('download-after', 'DOWNLOAD', 'Only posts published after a date',
      params=(_ARTIST, Param('date', 'date', '', 'published-after cutoff')))
def cmd_download_after(ctx: CLIContext, artist="", date=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    date = _ask_date(date, "Published after")
    if date and ctx.scheduler.queue_manual(artist.id, from_date=date):
        print(f"Queued {artist.display_name()} for posts after {date}.")


@_cmd('download-before', 'DOWNLOAD', 'Only posts published up to a date',
      params=(_ARTIST, Param('date', 'date', '', 'published-up-to cutoff')))
def cmd_download_before(ctx: CLIContext, artist="", date=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    date = _ask_date(date, "Published up to")
    if date and ctx.scheduler.queue_manual(artist.id, until_date=date):
        print(f"Queued {artist.display_name()} for posts up to {date}.")


@_cmd('download-between', 'DOWNLOAD', 'Only posts within a date range',
      params=(_ARTIST, Param('after', 'date', '', 'range start (exclusive)'),
              Param('before', 'date', '', 'range end (inclusive)')))
def cmd_download_between(ctx: CLIContext, artist="", after="", before=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    if not after and not before:
        after = ask("Published after: ")
        if after is None:
            return
        before = ask("Published up to: ")
        if before is None:
            return
    if ctx.scheduler.queue_manual(artist.id, from_date=after or None, until_date=before or None):
        print(f"Queued {artist.display_name()} [{after or '*'} .. {before or '*'}].")


# ============================================================================
# Sync
# ============================================================================

@_cmd('sync', 'SYNC', "Refresh one creator's cached post list (no files)",
      params=(_ARTIST, _DEEP))
def cmd_sync(ctx: CLIContext, artist="", deep=False):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    print("Syncing" + (" (deep: detecting edits)" if deep else "") + "...")
    new, edited = ctx.downloader.update_posts(artist, detect_edits=deep)
    s = ctx.cache.stats(artist.id)
    note = f", {edited} edited re-flagged" if deep else ""
    print(f"{'Updated' if new or edited else 'No change'}. "
          f"{s['done']}/{s['total']} done, {new} new{note}.")


@_cmd('sync-all', 'SYNC', 'Refresh all active creators (no files)', params=(_DEEP,))
def cmd_sync_all(ctx: CLIContext, deep=False):
    artists = get_artists(ctx, only_active=True)
    print(f"Syncing {len(artists)} creators" + (" (deep)" if deep else "") + "...")
    total_new = total_edited = 0
    for a in artists:
        try:
            new, edited = ctx.downloader.update_posts(a, detect_edits=deep)
            total_new += new
            total_edited += edited
        except Exception as e:
            print(f"  failed {a.display_name()}: {e}")
    note = f", {total_edited} edited re-flagged" if deep else ""
    print(f"Done. {total_new} new posts{note}.")


# ============================================================================
# Inspect
# ============================================================================

@_cmd('undone', 'INSPECT', "Show one creator's remaining posts", params=(_ARTIST,))
def cmd_undone(ctx: CLIContext, artist=""):
    artist = select_artist(ctx, artist)
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


_LINKS_PARAMS = (Param('match', 'str', '', 'keep only URLs matching this regex'),
                 Param('unique', 'bool', True, 'drop repeated URLs'),
                 Param('filtered', 'bool', True, 'apply the configured links_filter'))


def _links_filter(ctx: CLIContext, filtered: bool):
    """The configured link predicate, or None (filter empty or bypassed)."""
    if not filtered:
        return None
    flt = make_link_filter(ctx.storage.load_config().links_filter)
    if flt:
        print("(links_filter active — 'links-filter' to inspect, :filtered=false to bypass)")
    return flt


@_cmd('links', 'INSPECT', "External URLs in one creator's posts",
      params=(_ARTIST, *_LINKS_PARAMS))
def cmd_links(ctx: CLIContext, artist="", match="", unique=True, filtered=True):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    flt = _links_filter(ctx, filtered)
    _print_links(ctx, ctx.links_extractor.extract_from_artist(
        artist.id, match=match or None, unique=unique, filter_func=flt))


@_cmd('links-all', 'INSPECT', 'External URLs across all creators', params=_LINKS_PARAMS)
def cmd_links_all(ctx: CLIContext, match="", unique=True, filtered=True):
    flt = _links_filter(ctx, filtered)
    all_links = []
    for a in get_artists(ctx):
        all_links.extend(ctx.links_extractor.extract_from_artist(
            a.id, match=match or None, unique=unique, filter_func=flt))
    _print_links(ctx, all_links)


@_cmd('links-filter', 'INSPECT', 'Show the links filter; optionally set its cutoff date',
      params=(Param('cutoff', 'date', '', 'set reviewed_before to this date'),))
def cmd_links_filter(ctx: CLIContext, cutoff=""):
    config = ctx.storage.load_config()
    lf = dict(config.links_filter or {})
    if cutoff:
        lf['reviewed_before'] = cutoff
        config.links_filter = lf
        ctx.storage.save_config(config)
        print(f"reviewed_before -> {cutoff}")

    domains = lf.get('allowed_domains') or []
    reviewed = lf.get('reviewed_artists') or []
    print(f"\nlinks_filter: {'active' if domains or reviewed else 'inactive (shows everything)'}")
    if domains:
        head = ', '.join(domains[:6]) + (' ...' if len(domains) > 6 else '')
        print(f"  allowed_domains   {len(domains)}: {head}")
    else:
        print("  allowed_domains   (any domain)")
    print(f"  reviewed_before   {lf.get('reviewed_before') or '- (reviewed artists fully hidden)'}")
    print(f"  reviewed_artists  {len(reviewed)}")
    if reviewed:
        known = {a.id: a for a in ctx.storage.get_artists()}
        for aid in reviewed:
            name = known[aid].display_name() if aid in known else '(not tracked here)'
            print(f"    {aid}  {name}")
    print("\nallowed_domains is edited in data/config.json (links_filter section);"
          "\n'links-reviewed' marks a creator's links as gone through.")


@_cmd('links-reviewed', 'INSPECT', "Mark a creator's links reviewed (hidden up to the cutoff)",
      params=(_ARTIST, Param('remove', 'bool', False, 'unmark instead of marking')))
def cmd_links_reviewed(ctx: CLIContext, artist="", remove=False):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    config = ctx.storage.load_config()
    lf = dict(config.links_filter or {})
    reviewed = list(lf.get('reviewed_artists') or [])

    if remove:
        if artist.id not in reviewed:
            print(f"{artist.display_name()} was not marked reviewed.")
            return
        reviewed.remove(artist.id)
        print(f"{artist.display_name()} unmarked; its links show again.")
    else:
        if artist.id in reviewed:
            print(f"{artist.display_name()} is already marked reviewed.")
            return
        reviewed.append(artist.id)
        cutoff = lf.get('reviewed_before')
        if cutoff:
            print(f"{artist.display_name()} marked reviewed; posts after {cutoff} still show.")
        else:
            print(f"{artist.display_name()} marked reviewed; all its links are now hidden "
                  f"(set links-filter:cutoff=... to keep new posts visible).")

    lf['reviewed_artists'] = reviewed
    config.links_filter = lf
    ctx.storage.save_config(config)


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


@_cmd('download-gdrive', 'INSPECT', 'Download found Google Drive links (needs gdown)',
      params=(Param('match', 'str', '', 'extra regex filter'),))
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
    if not confirm("Download them with gdown?"):
        return
    ctx.links_downloader.download_gdrive_links(urls)


# ============================================================================
# Maintain
# ============================================================================

_AFTER_DATE = Param('after_date', 'date', '', 'only posts published after this date')


@_cmd('reset', 'MAINTAIN', "Mark one creator's posts undone",
      params=(_ARTIST, _AFTER_DATE))
def cmd_reset(ctx: CLIContext, artist="", after_date=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    n = ctx.cache.reset_after_date(artist.id, after_date or None)
    print(f"Reset {n} posts for {artist.display_name()}.")


@_cmd('reset-all', 'MAINTAIN', "Mark every creator's posts undone", params=(_AFTER_DATE,))
def cmd_reset_all(ctx: CLIContext, after_date=""):
    if not confirm("Reset posts for ALL artists?"):
        return
    total = sum(ctx.cache.reset_after_date(a.id, after_date or None)
                for a in ctx.storage.get_artists())
    print(f"Reset {total} posts.")


@_cmd('reset-conflicts', 'MAINTAIN', 'Undo posts whose output paths collide',
      params=(_ARTIST,))
def cmd_reset_conflicts(ctx: CLIContext, artist=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    n = ctx.validator.reset_conflicts(artist)
    print(f"Reset {n} conflicting posts to undone.")


@_cmd('reset-conflicts-all', 'MAINTAIN', 'Undo colliding posts for every creator')
def cmd_reset_conflicts_all(ctx: CLIContext):
    total = sum(ctx.validator.reset_conflicts(a) for a in ctx.storage.get_artists())
    print(f"Reset {total} conflicting posts across all artists.")


@_cmd('dedupe', 'MAINTAIN', 'Remove duplicate cached posts', params=(_ARTIST,))
def cmd_dedupe(ctx: CLIContext, artist=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    print(f"Removed {ctx.cache.deduplicate(artist.id)} duplicates.")


@_cmd('dedupe-all', 'MAINTAIN', 'Remove duplicate cached posts for every creator')
def cmd_dedupe_all(ctx: CLIContext):
    total = sum(ctx.cache.deduplicate(a.id) for a in ctx.storage.get_artists())
    print(f"Removed {total} duplicates total.")


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


@_cmd('validate', 'MAINTAIN', "Report one creator's colliding output paths",
      params=(_ARTIST,))
def cmd_validate(ctx: CLIContext, artist=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    _print_conflicts(ctx.validator.find_conflicts([artist]))


@_cmd('validate-all', 'MAINTAIN', 'Report colliding output paths everywhere')
def cmd_validate_all(ctx: CLIContext):
    print("Checking all artists for output-path collisions...")
    _print_conflicts(ctx.validator.find_conflicts(ctx.storage.get_artists()))


_CLEAN_PARAMS = (Param('quarantine', 'str', '_invalid', 'folder orphans are moved into'),
                 Param('dry', 'bool', True, 'preview only; use dry=false to apply'))


@_cmd('clean-folders', 'MAINTAIN', 'Quarantine orphan download folders',
      params=(_ARTIST, *_CLEAN_PARAMS))
def cmd_clean_folders(ctx: CLIContext, artist="", quarantine="_invalid", dry=True):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    _clean_one(ctx, artist, quarantine, dry)


@_cmd('clean-folders-all', 'MAINTAIN', 'Quarantine orphan folders for every active creator',
      params=_CLEAN_PARAMS)
def cmd_clean_folders_all(ctx: CLIContext, quarantine="_invalid", dry=True):
    for a in get_artists(ctx, only_active=True):
        _clean_one(ctx, a, quarantine, dry)


def _clean_one(ctx: CLIContext, artist, quarantine, dry):
    moves = ctx.validator.clean_post_folders(artist, quarantine=quarantine, dry=dry)
    if not moves:
        return
    verb = "Would move" if dry else "Moved"
    print(f"{artist.display_name()}: {verb} {len(moves)} orphan folder(s) -> {quarantine}/")
    for src, _dst in moves[:10]:
        print(f"    {Path(src).name}")
    if dry:
        print("    (dry run; re-run with :dry=false to apply)")


def _migration_config(ctx: CLIContext, artist, prompt_label) -> Optional[MigrationConfig]:
    """Prompt for the templates of one side of a migration, defaulting to the
    artist's effective (config-merged) templates. None means cancelled."""
    cv = lambda k: get_config_value(artist, ctx.storage.load_config(), k)
    print(f"\n{prompt_label} templates (blank = current effective value):")
    values = {}
    for key in ('artist_folder_template', 'post_folder_template', 'file_template'):
        raw = ask(f"  {key} [{cv(key)}]: ", default=cv(key))
        if raw is None:
            return None
        values[key] = raw
    return MigrationConfig(
        download_dir=cv('download_dir'),
        artist_folder_template=values['artist_folder_template'],
        post_folder_template=values['post_folder_template'],
        file_template=values['file_template'],
        date_format=cv('date_format'), rename_images_only=cv('rename_images_only'),
        image_extensions=ctx.storage.load_config().image_extensions,
    )


def _run_migration(ctx: CLIContext, kind: str, query: str):
    artist = select_artist(ctx, query)
    if not artist:
        return
    old = _migration_config(ctx, artist, "OLD (where files are now)")
    if old is None:
        return
    new = _migration_config(ctx, artist, "NEW (where they should go)")
    if new is None:
        return
    plan = (ctx.migrator.plan_posts if kind == "post" else ctx.migrator.plan_files)(artist, old, new)
    print(f"\nPlan: {plan.success_count} to move, {len(plan.conflicts)} conflicts, "
          f"{len(plan.skipped)} skipped (of {plan.total_items}).")
    for src, dst, _id in plan.mappings[:10]:
        print(f"  {src}\n    -> {dst}")
    if plan.success_count > 10:
        print(f"  ... and {plan.success_count - 10} more")
    if not plan.mappings:
        return
    if not confirm(f"\nApply {plan.success_count} moves?"):
        return
    result = ctx.migrator.execute(plan)
    print(f"Moved {result.success}/{result.total}. Failed: {len(result.failed)}.")


@_cmd('relayout-posts', 'MAINTAIN', 'Move post folders to match new templates',
      params=(_ARTIST,))
def cmd_relayout_posts(ctx: CLIContext, artist=""):
    _run_migration(ctx, "post", artist)


@_cmd('relayout-files', 'MAINTAIN', 'Rename files to match new templates',
      params=(_ARTIST,))
def cmd_relayout_files(ctx: CLIContext, artist=""):
    _run_migration(ctx, "file", artist)


# ============================================================================
# Tasks & Config
# ============================================================================

@_cmd('tasks', 'TASKS & CONFIG', 'Show the download queue')
def cmd_tasks(ctx: CLIContext):
    st = ctx.scheduler.status()
    print(f"\nQueued: {st['queued']}  Running: {st['running']}  Completed: {st['completed']}")
    active = ctx.scheduler.list_active()
    if active:
        print("\nRunning:")
        for t in active:
            print(f"  [{t.task_type}] {_task_label(ctx, t)}")
    queued = ctx.scheduler.list_queued()
    if queued:
        print("\nQueued:")
        for t in queued[:20]:
            print(f"  [{t.task_type}] {_task_label(ctx, t)}")
    recent = ctx.scheduler.completed[-10:]
    if recent:
        print("\nRecent:")
        for t in reversed(recent):
            err = f" ({t.error})" if t.error else ""
            print(f"  [{t.status}] {_task_label(ctx, t)}{err}")


def _task_label(ctx: CLIContext, task) -> str:
    artist = ctx.storage.get_artist(task.artist_id)
    return artist.display_name() if artist else task.artist_id


@_cmd('cancel', 'TASKS & CONFIG', 'Cancel one queued or running download',
      params=(Param('artist', 'str', '', 'task to cancel; picked from a list if omitted'),))
def cmd_cancel(ctx: CLIContext, artist=""):
    active = ctx.scheduler.list_active()
    queued = ctx.scheduler.list_queued()
    tasks = [('running', t) for t in active] + [('queued', t) for t in queued]
    if not tasks:
        print("Nothing to cancel.")
        return

    raw = artist
    if not raw:
        print("\nCancellable downloads:")
        for i, (state, t) in enumerate(tasks, 1):
            print(f"  {i}. [{state}] {_task_label(ctx, t)}")
        raw = ask("\nCancel which (number/id, Enter to abort): ")
        if raw is None or not raw:
            return

    if raw.isdigit() and 1 <= int(raw) <= len(tasks):
        artist_id = tasks[int(raw) - 1][1].artist_id
    else:
        low = raw.lower()
        artist_id = next((t.artist_id for _, t in tasks
                          if t.artist_id.lower() == low or _task_label(ctx, t).lower() == low), None)
        if not artist_id:
            raise CommandError(f"No queued or running task matches '{raw}'.")

    state = ctx.scheduler.cancel(artist_id)
    if state:
        print(f"Cancelled {artist_id} ({state}).")
    else:
        print(f"{artist_id} was no longer active.")


@_cmd('cancel-all', 'TASKS & CONFIG', 'Cancel every queued & running download')
def cmd_cancel_all(ctx: CLIContext):
    n = ctx.scheduler.cancel_all()
    print(f"Cancelled all. {n} were running.")


@_cmd('config', 'TASKS & CONFIG', 'Edit global settings interactively')
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
        val = ask(f"  {key} [{current}]: ")
        if val is None:
            print("Cancelled; nothing saved.")
            return
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


@_cmd('config-artist', 'TASKS & CONFIG', 'Edit per-creator overrides', params=(_ARTIST,))
def cmd_config_artist(ctx: CLIContext, artist=""):
    artist = select_artist(ctx, artist)
    if not artist:
        return
    keys = ['artist_folder_template', 'post_folder_template', 'file_template',
            'date_format', 'save_content', 'download_dir']
    print(f"\nOverrides for {artist.display_name()} (blank = keep, '-' = clear):")
    for key in keys:
        current = artist.config.get(key, "(inherit)")
        val = ask(f"  {key} [{current}]: ")
        if val is None:
            print("Cancelled; nothing saved.")
            return
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


@_cmd('config-conflicts', 'TASKS & CONFIG', 'Manage muted path conflicts')
def cmd_config_conflicts(ctx: CLIContext):
    data = ctx.validator.load_ignores()
    ignored = data.get('ignored_paths', [])
    print(f"\nMuted conflict paths: {len(ignored)}")
    for p in ignored[:50]:
        print(f"  {p}")
    print("\nActions: [c]lear all, [a]dd current conflicts, [Enter] cancel")
    choice = (ask("> ") or "").lower()
    if choice == 'c':
        ctx.validator.clear_ignores()
        print("Cleared.")
    elif choice == 'a':
        conflicts = ctx.validator.find_conflicts(ctx.storage.get_artists())
        ctx.validator.ignore_paths([p for p, _ in conflicts])
        print(f"Muted {len(conflicts)} current conflicts.")


# ============================================================================
# Session
# ============================================================================

@_cmd('history', 'SESSION', 'Recent commands',
      params=(Param('limit', 'int', 10, 'how many entries'),))
def cmd_history(ctx: CLIContext, limit=10):
    for r in ctx.storage.get_history(limit):
        mark = "ok " if r.success else "ERR"
        extra = f" {r.params}" if r.params else ""
        print(f"  [{mark}] {r.timestamp[:19]} {r.command}{extra}")


@_cmd('test', 'SESSION', 'Verify the plugin system is loading')
def cmd_test(ctx: CLIContext):
    from ..common.hotreload import dynamic_call
    try:
        result = dynamic_call('test_plugin', 'src/plugins/test_plugin.py',
                              default=lambda: "(no plugin)")
        print(f"Plugin test result: {result() if callable(result) else result}")
    except Exception as e:
        print(f"Plugin test failed: {e}")


@_cmd('help', 'SESSION', 'This overview, or details for one command',
      params=(Param('command', 'str', '', 'show usage details for this command'),))
def cmd_help(ctx: CLIContext, command=""):
    if command:
        _help_detail(command)
        return
    print("\nPawchive Downloader — command:key=value,key=value   (or: command value)")
    print("A unique prefix works ('hist' -> history); Tab completes names.\n")
    group = None
    for cmd in _REGISTRY:
        if cmd.group != group:
            group = cmd.group
            print(f"  {group}")
        display = cmd.name + (f" | {' | '.join(cmd.aliases)}" if cmd.aliases else "")
        if cmd.params:
            display += " :" + ",".join(p.name for p in cmd.params)
        print(f"    {display:<42} {cmd.summary}")
    print("\n  'help <command>' shows a command's parameters and defaults.")


def _help_detail(name: str):
    from .registry import resolve
    cmd = resolve(COMMAND_MAP, name)
    print(f"\n{cmd.name} — {cmd.summary}")
    if cmd.aliases:
        print(f"  aliases: {', '.join(cmd.aliases)}")
    if not cmd.params:
        print("  takes no parameters")
        return
    print(f"  usage: {cmd.signature()}")
    for p in cmd.params:
        default = f" (default {p.default!r})" if p.default not in ('', None) else ""
        print(f"    {p.name:<12} {p.kind:<5} {p.help}{default}")


@_cmd('clear', 'SESSION', 'Clear the screen')
def cmd_clear(ctx: CLIContext):
    print("\033[2J\033[H", end="")


@_cmd('exit', 'SESSION', 'Quit', aliases=('quit',))
def cmd_exit(ctx: CLIContext):
    raise ExitShell()


COMMAND_MAP = build_map(_REGISTRY)
