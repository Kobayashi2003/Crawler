import json
import threading
from pathlib import Path
from typing import List, Optional

from .models import Artist, Config, HistoryRecord


class Storage:
    """Persists artists, config and command history as JSON under `data_dir`.

    Artists live in `artists.json`. As a convenience, any `*.json` files under
    `data/artists/` are also loaded (read-only, deduped by id) so creators can
    be organised into folders; `artists.json` always wins on conflicts.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artists_dir = self.data_dir / "artists"
        self.artists_file = self.data_dir / "artists.json"
        self.config_file = self.data_dir / "config.json"
        self.history_file = self.data_dir / "history.json"
        self.lock = threading.RLock()
        self._ensure_files()

    def _ensure_files(self):
        for path, default in (
            (self.artists_file, "[]"),
            (self.config_file, "{}"),
            (self.history_file, "[]"),
        ):
            if not path.exists():
                path.write_text(default, encoding='utf-8')

    # ==================== Config ====================

    def load_config(self) -> Config:
        with self.lock:
            data = json.loads(self.config_file.read_text(encoding='utf-8'))
            if not data:
                return Config()
            if isinstance(data.get('image_extensions'), list):
                data['image_extensions'] = set(data['image_extensions'])
            # Ignore unknown keys so stale configs don't crash startup.
            valid = Config.__dataclass_fields__.keys()
            return Config(**{k: v for k, v in data.items() if k in valid})

    def save_config(self, config: Config):
        with self.lock:
            data = dict(config.__dict__)
            if isinstance(data.get('image_extensions'), set):
                data['image_extensions'] = sorted(data['image_extensions'])
            self.config_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8'
            )

    # ==================== Artists ====================

    def _read_primary(self) -> List[Artist]:
        data = json.loads(self.artists_file.read_text(encoding='utf-8'))
        return [Artist(**item) for item in data]

    def _write_primary(self, artists: List[Artist]):
        self.artists_file.write_text(
            json.dumps([a.__dict__ for a in artists], indent=2, ensure_ascii=False),
            encoding='utf-8',
        )

    def get_artists(self) -> List[Artist]:
        with self.lock:
            artists = self._read_primary()
            seen = {a.id for a in artists}

            if self.artists_dir.is_dir():
                for path in sorted(self.artists_dir.rglob('*.json')):
                    try:
                        content = json.loads(path.read_text(encoding='utf-8'))
                    except Exception:
                        continue
                    items = content if isinstance(content, list) else [content]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        aid = item.get('id')
                        if aid and aid not in seen:
                            artists.append(Artist(**item))
                            seen.add(aid)
            return artists

    def get_artist(self, artist_id: str) -> Optional[Artist]:
        return next((a for a in self.get_artists() if a.id == artist_id), None)

    def save_artist(self, artist: Artist):
        with self.lock:
            # Update in place if present in artists.json.
            artists = self._read_primary()
            for i, a in enumerate(artists):
                if a.id == artist.id:
                    artists[i] = artist
                    self._write_primary(artists)
                    return

            # Otherwise, try to update within the artists/ folder tree.
            if self._update_in_subdir(artist):
                return

            # New artist: append to artists.json.
            artists.append(artist)
            self._write_primary(artists)

    def _update_in_subdir(self, artist: Artist) -> bool:
        if not self.artists_dir.is_dir():
            return False
        for path in sorted(self.artists_dir.rglob('*.json')):
            try:
                content = json.loads(path.read_text(encoding='utf-8'))
            except Exception:
                continue
            changed = False
            if isinstance(content, dict) and content.get('id') == artist.id:
                content = artist.__dict__
                changed = True
            elif isinstance(content, list):
                for idx, item in enumerate(content):
                    if isinstance(item, dict) and item.get('id') == artist.id:
                        content[idx] = artist.__dict__
                        changed = True
                        break
            if changed:
                path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding='utf-8')
                return True
        return False

    def remove_artist(self, artist_id: str):
        with self.lock:
            artists = self._read_primary()
            remaining = [a for a in artists if a.id != artist_id]
            if len(remaining) != len(artists):
                self._write_primary(remaining)
                return

            if not self.artists_dir.is_dir():
                return
            for path in sorted(self.artists_dir.rglob('*.json')):
                try:
                    content = json.loads(path.read_text(encoding='utf-8'))
                except Exception:
                    continue
                if isinstance(content, dict) and content.get('id') == artist_id:
                    path.unlink(missing_ok=True)
                    return
                if isinstance(content, list):
                    new = [i for i in content if not (isinstance(i, dict) and i.get('id') == artist_id)]
                    if len(new) != len(content):
                        path.write_text(json.dumps(new, indent=2, ensure_ascii=False), encoding='utf-8')
                        return

    # ==================== History ====================

    def add_history(self, command: str, success: bool = True, artist_id: str = None,
                    params: dict = None, note: str = ""):
        with self.lock:
            data = json.loads(self.history_file.read_text(encoding='utf-8'))
            data.append(HistoryRecord(
                command=command, success=success, artist_id=artist_id,
                params=params or {}, note=note,
            ).__dict__)
            self.history_file.write_text(
                json.dumps(data[-500:], indent=2, ensure_ascii=False), encoding='utf-8'
            )

    def get_history(self, limit: int = 10) -> List[HistoryRecord]:
        with self.lock:
            data = json.loads(self.history_file.read_text(encoding='utf-8'))
            return [HistoryRecord(**item) for item in data[-limit:]][::-1]

    def clear_history(self):
        with self.lock:
            self.history_file.write_text("[]", encoding='utf-8')
