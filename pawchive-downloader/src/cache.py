import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .filters import PostFilter
from .logger import Logger
from .models import Artist, Config, Post, Profile
from .storage import Storage


class Cache:
    """Per-artist on-disk cache of the post list and profile.

    Each artist has two files under `cache_dir`:
        {artist_id}_posts.json    - list of Post dicts incl. `done` state
        {artist_id}_profile.json  - last seen Profile (used for change detection)

    Mutations always operate on the *unfiltered* post list; filters are a
    read-time view so filtered-out posts are never dropped from disk.
    """

    def __init__(self, cache_dir: str, logger: Logger, config: Config, storage: Storage):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self.config = config
        self.storage = storage
        self.lock = threading.RLock()

    def _posts_path(self, artist_id: str) -> Path:
        return self.cache_dir / f"{artist_id}_posts.json"

    def _profile_path(self, artist_id: str) -> Path:
        return self.cache_dir / f"{artist_id}_profile.json"

    # ==================== Profile ====================

    def save_profile(self, artist_id: str, data: Dict):
        with self.lock:
            valid = Profile.__dataclass_fields__.keys()
            profile = Profile(**{k: v for k, v in data.items() if k in valid})
            profile.cached_at = datetime.now().isoformat()
            self._profile_path(artist_id).write_text(
                json.dumps(profile.__dict__, indent=2, ensure_ascii=False), encoding='utf-8'
            )

    def load_profile(self, artist_id: str) -> Optional[Profile]:
        with self.lock:
            path = self._profile_path(artist_id)
            if not path.exists():
                return None
            try:
                return Profile(**json.loads(path.read_text(encoding='utf-8')))
            except Exception:
                return None

    # ==================== Posts ====================

    def _save_posts(self, artist_id: str, posts: List[Post]):
        self._posts_path(artist_id).write_text(
            json.dumps([p.__dict__ for p in posts], indent=2, ensure_ascii=False), encoding='utf-8'
        )

    def save_posts(self, artist_id: str, posts: List[Post]):
        with self.lock:
            self._save_posts(artist_id, posts)

    def _load_posts_raw(self, artist_id: str) -> List[Post]:
        path = self._posts_path(artist_id)
        if not path.exists():
            return []
        try:
            return [Post(**item) for item in json.loads(path.read_text(encoding='utf-8'))]
        except Exception:
            return []

    def load_posts(self, artist_id: str, apply_filters: bool = True) -> List[Post]:
        with self.lock:
            posts = self._load_posts_raw(artist_id)
            if not apply_filters or not posts:
                return posts

            artist = self.storage.get_artist(artist_id)
            if not isinstance(artist, Artist):
                return posts
            filter_cfg = {**self.config.global_filter, **artist.filter}
            if not filter_cfg:
                return posts

            filtered = PostFilter.apply(posts, filter_cfg)
            removed = len(posts) - len(filtered)
            if removed:
                self.logger.cache_filtered(artist=artist.display_name(), removed=removed)
            return filtered

    def update_post(self, artist_id: str, post_id: str, done: bool,
                    failed_files: List[str] = None, content: str = None):
        with self.lock:
            posts = self._load_posts_raw(artist_id)
            for p in posts:
                if p.id == post_id:
                    p.done = done
                    if failed_files is not None:
                        p.failed_files = failed_files
                    if content is not None:
                        p.content = content
                    break
            self._save_posts(artist_id, posts)

    # ==================== Queries ====================

    def get_undone(self, artist_id: str) -> List[Post]:
        return [p for p in self.load_posts(artist_id) if not p.done or p.failed_files]

    def stats(self, artist_id: str) -> Dict:
        posts = self.load_posts(artist_id)
        total = len(posts)
        done = sum(1 for p in posts if p.done)
        failed = sum(1 for p in posts if p.failed_files)
        return {'total': total, 'done': done, 'pending': total - done, 'failed': failed}

    # ==================== Maintenance ====================

    def reset_after_date(self, artist_id: str, after_date: str = None) -> int:
        with self.lock:
            posts = self._load_posts_raw(artist_id)
            count = 0
            for p in posts:
                if not p.published or not p.done:
                    continue
                if after_date is None or p.published > after_date:
                    p.done = False
                    p.failed_files = []
                    count += 1
            if count:
                self._save_posts(artist_id, posts)
                self.logger.cache_reset(artist_id=artist_id, after=after_date or 'all', count=count)
            return count

    def deduplicate(self, artist_id: str) -> int:
        with self.lock:
            posts = self._load_posts_raw(artist_id)
            seen = set()
            unique = []
            for p in posts:
                if p.id not in seen:
                    seen.add(p.id)
                    unique.append(p)
            removed = len(posts) - len(unique)
            if removed:
                self._save_posts(artist_id, unique)
                self.logger.cache_dedupe(artist_id=artist_id, removed=removed)
            return removed
