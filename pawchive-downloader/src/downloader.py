import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

from .api import API
from .cache import Cache
from .formatter import Formatter, extract_files, get_config_value
from .logger import Logger
from .models import Artist, Config, DownloadResult, NO_CONTENT_MARKER, Post
from .storage import Storage


class Downloader:
    """Drives the fetch → cache → download pipeline for artists.

    Unlike the kemono predecessor, Pawchive's post-list response already
    includes each post's ``content``, ``file`` and ``attachments``, so there is
    no per-post detail round-trip: the cached list is authoritative.
    """

    def __init__(self, config: Config, logger: Logger, storage: Storage, cache: Cache, api: API):
        self.config = config
        self.logger = logger
        self.storage = storage
        self.cache = cache
        self.api = api
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()
        self.api.stop()

    def resume(self):
        self._stop.clear()
        self.api.resume()

    # ==================== Cache refresh ====================

    def update_posts(self, artist: Artist) -> bool:
        """Refresh the cached post list if the creator changed.

        Pawchive has no post count, so we diff the profile ``updated`` timestamp
        against the cached profile; when it differs (or the cache is empty) we
        re-page the full list and merge, preserving ``done`` state and never
        dropping cached posts the API transiently omits.
        """
        if self._stop.is_set() or artist.completed or artist.ignore:
            return False

        profile = self.api.get_profile_until_success(artist.service, artist.user_id)
        cached_posts = self.cache.load_posts(artist.id, apply_filters=False)
        cached_profile = self.cache.load_profile(artist.id)

        if (cached_posts and cached_profile
                and cached_profile.updated
                and cached_profile.updated == profile.get('updated')):
            self.logger.downloader_no_new(artist=artist.display_name())
            return False

        raw = self.api.get_all_posts(artist.service, artist.user_id)

        # De-dupe by id, keeping first-seen order.
        by_id: Dict[str, Dict] = {}
        for item in raw:
            by_id.setdefault(str(item.get('id')), item)
        api_ids = set(by_id.keys())

        existing = {str(p.id): p for p in cached_posts}
        is_new_artist = not cached_posts
        merged: List[Post] = []
        new_count = 0

        for data in by_id.values():
            pid = str(data['id'])
            if pid in existing:
                merged.append(existing[pid])
                continue

            post = Post(
                id=pid,
                user=str(data.get('user', artist.user_id)),
                service=data.get('service', artist.service),
                title=data.get('title', ''),
                content=data.get('content', ''),
                published=data.get('published', ''),
                added=data.get('added', ''),
                edited=data.get('edited'),
                file=data.get('file') or None,
                attachments=data.get('attachments') or [],
            )
            # Only auto-mark old posts done when first adding an artist; for an
            # existing artist, backfilled old posts should still download.
            if is_new_artist and artist.last_date and post.published <= artist.last_date:
                post.done = True
            else:
                new_count += 1
            merged.append(post)

        # Keep cached posts the API omitted this time (transient gaps).
        missing = [p for p in cached_posts if str(p.id) not in api_ids]
        if missing:
            merged.extend(missing)
            self.logger.downloader_list_incomplete(
                artist=artist.display_name(), missing=len(missing), level='warning'
            )

        self.cache.save_posts(artist.id, merged)
        self.cache.save_profile(artist.id, profile)

        if new_count == 0 and not missing:
            self.logger.downloader_no_new(artist=artist.display_name())
            return False
        self.logger.downloader_cached(artist=artist.display_name(), total=len(merged), new=new_count)
        return True

    # ==================== Download ====================

    def download_artist(self, artist: Artist, from_date: Optional[str] = None,
                        until_date: Optional[str] = None) -> DownloadResult:
        try:
            if self._stop.is_set():
                return DownloadResult(artist.id, skipped=True)
            if artist.completed or artist.ignore:
                self.logger.downloader_skipped(
                    artist=artist.display_name(),
                    status='completed' if artist.completed else 'ignored',
                )
                return DownloadResult(artist.id, skipped=True)

            self.update_posts(artist)

            if from_date or until_date:
                posts = [
                    p for p in self.cache.load_posts(artist.id)
                    if (not from_date or p.published > from_date)
                    and (not until_date or p.published <= until_date)
                ]
            else:
                posts = self.cache.get_undone(artist.id)

            if not posts:
                self.logger.downloader_nothing(artist=artist.display_name())
                result = DownloadResult(artist.id, success=True)
            else:
                result = self._download_posts(artist, posts)

            new_last = self._calc_last_date(artist)
            if new_last and new_last > (artist.last_date or ""):
                artist.last_date = new_last
                self.storage.save_artist(artist)
                self.logger.downloader_last_date(artist=artist.display_name(), last_date=new_last)

            return result
        except InterruptedError:
            return DownloadResult(artist.id, skipped=True)
        except Exception as e:
            self.logger.downloader_artist_failed(artist=artist.display_name(), error=str(e), level='error')
            return DownloadResult(artist.id, success=False)

    def _download_posts(self, artist: Artist, posts: List[Post]) -> DownloadResult:
        self.logger.downloader_processing(artist=artist.display_name(), count=len(posts))
        downloaded = 0
        failed = 0
        lock = threading.Lock()

        def process(item):
            idx, post = item
            if self._stop.is_set():
                return False
            try:
                ok = self._download_post(artist, post)
                if ok:
                    self.cache.update_post(
                        artist.id, post.id, done=True, failed_files=[],
                        content=(post.content or None),
                    )
                return ok
            except Exception as e:
                self.logger.downloader_post_error(post_id=post.id, error=str(e), level='error')
                return False

        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_posts) as executor:
            futures = [executor.submit(process, (i, p)) for i, p in enumerate(posts, 1)]
            for future in as_completed(futures):
                if future.result():
                    with lock:
                        downloaded += 1
                else:
                    with lock:
                        failed += 1

        self.logger.downloader_completed(
            artist=artist.display_name(), succeeded=downloaded, failed=failed
        )
        return DownloadResult(artist.id, success=(failed == 0),
                              posts_downloaded=downloaded, posts_failed=failed)

    def _download_post(self, artist: Artist, post: Post) -> bool:
        cv = lambda k: get_config_value(artist, self.config, k)
        download_dir = cv('download_dir')
        save_content = cv('save_content')
        save_empty = cv('save_empty_posts')

        files = extract_files(post)
        if not files and not save_empty and not save_content:
            return True

        artist_folder = Formatter.artist_folder(artist, cv('artist_folder_template'))
        post_folder = Formatter.post_folder(post, cv('post_folder_template'), cv('date_format'))
        save_dir = Path(download_dir) / artist_folder / post_folder
        save_dir.mkdir(parents=True, exist_ok=True)

        if save_content and post.content and post.content != NO_CONTENT_MARKER:
            (save_dir / "content.txt").write_text(post.content, encoding='utf-8', errors='ignore')

        if not files:
            return True

        names = Formatter.file_names(
            [f['name'] for f in files], cv('file_template'),
            cv('rename_images_only'), self.config.image_extensions,
        )

        failed_files: List[str] = []
        lock = threading.Lock()

        def dl(pair):
            file, name = pair
            if self._stop.is_set():
                return (False, name)
            try:
                url = API.file_url(file['path'], file['name'])
                self.api.download_file_until_success(url, str(save_dir / name))
                self.logger.downloader_file_ok(file=name)
                return (True, name)
            except Exception as e:
                self.logger.downloader_file_failed(file=name, error=str(e), level='warning')
                return (False, name)

        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_files) as executor:
            futures = [executor.submit(dl, (f, n)) for f, n in zip(files, names)]
            for future in as_completed(futures):
                ok, name = future.result()
                if not ok:
                    with lock:
                        failed_files.append(name)

        if failed_files:
            self.cache.update_post(artist.id, post.id, done=False, failed_files=failed_files)
            return False
        return True

    # ==================== Helpers ====================

    def _calc_last_date(self, artist: Artist) -> Optional[str]:
        """Advance last_date over the run of oldest→newest posts that are done."""
        posts = sorted(self.cache.load_posts(artist.id), key=lambda p: p.published)
        start = artist.last_date or ""
        new_last = start
        for post in posts:
            if post.published <= start:
                continue
            if not post.done:
                break
            new_last = post.published
        return new_last if new_last != start else None
