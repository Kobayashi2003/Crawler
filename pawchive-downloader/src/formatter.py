import re
from datetime import datetime
from pathlib import Path
from typing import List

from .models import Artist, Config, Post
from .plugins import plugin_hook

# Optional user plugin; each hook is resolved per call so edits hot-reload.
# See plugins/format_plugin.py for the contract (all hooks are no-ops by default).
_FORMAT_PLUGIN = 'plugins/format_plugin.py'


class Formatter:
    """Builds sanitized download paths in three levels:

        download_dir / artist_folder / post_folder / file_name

    Templates use ``str.format`` fields; every produced segment is sanitized so
    it is safe to use as a Windows path component. Each level can be customised
    by an optional hot-reloadable plugin (see ``plugins/format_plugin.py``).
    """

    # ==================== Level 1: artist folder ====================

    @staticmethod
    @plugin_hook('format_artist_plugin', _FORMAT_PLUGIN)
    def artist_folder(artist: Artist, template: str) -> Path:
        raw = template.format(
            service=artist.service,
            name=artist.name,
            alias=(artist.alias or artist.name),
            user_id=artist.user_id,
            last_date=(artist.last_date[:10] if artist.last_date else ""),
        )
        return Path(Formatter._sanitize_path(raw))

    # ==================== Level 2: post folder ====================

    @staticmethod
    @plugin_hook('format_post_plugin', _FORMAT_PLUGIN)
    def post_folder(post: Post, template: str, date_format: str) -> str:
        raw = template.format(
            id=post.id,
            user=post.user,
            service=post.service,
            title=post.title,
            published=Formatter._format_date(post.published, date_format),
        )
        return Formatter._sanitize(raw)

    # ==================== Level 3: file names ====================

    @staticmethod
    @plugin_hook('format_file_plugin', _FORMAT_PLUGIN)
    def format_file(name: str, idx: int, template: str) -> str:
        """Format one file name from ``template`` (fields: ``idx``, ``name``)."""
        out = template.format(idx=idx, name=name)
        if '.' not in out and '.' in name:
            out = f"{out}.{name.rsplit('.', 1)[-1]}"
        return Formatter._sanitize(out)

    @staticmethod
    def file_names(names: List[str], template: str,
                   rename_images_only: bool, image_extensions: set) -> List[str]:
        """Format a post's file names, honouring ``rename_images_only``.

        Non-image files keep their original name when ``rename_images_only`` is
        set; image files are renamed via ``template`` with a 0-based ``{idx}``.
        """
        result = []
        image_index = 0
        for i, original in enumerate(names):
            ext = Path(original).suffix.lower()
            is_image = ext in image_extensions
            should_rename = not rename_images_only or is_image

            if should_rename:
                idx = image_index if (rename_images_only and is_image) else i
                if is_image:
                    image_index += 1
                result.append(Formatter.format_file(original, idx, template))
            else:
                result.append(Formatter._sanitize(original))
        return result

    # ==================== Private ====================

    _FORBIDDEN = {
        '/': '／', '\\': '＼', ':': '：', '*': '＊', '?': '？',
        '"': '＂', '<': '＜', '>': '＞', '|': '｜',
        '　': ' ', ' ': ' ', '\t': ' ', '\r': ' ', '\n': ' ',
        '​': '', '‌': '', '‍': '', '﻿': '',
        '‎': '', '‏': '',
    }

    @staticmethod
    def _sanitize(text: str) -> str:
        if not text:
            return "unknown"
        text = re.sub(r'[\x00-\x1F\x7F]', '', text)
        for ch, repl in Formatter._FORBIDDEN.items():
            text = text.replace(ch, repl)
        text = re.sub(r' +', ' ', text).strip(' .')
        return text or "unknown"

    @staticmethod
    def _sanitize_path(path_str: str) -> str:
        segments = path_str.replace('\\', '/').split('/')
        return '/'.join(Formatter._sanitize(s) for s in segments)

    @staticmethod
    def _format_date(date_str: str, date_format: str) -> str:
        if not date_str:
            return ""
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime(date_format)
        except Exception:
            return date_str[:10]


def get_config_value(artist: Artist, config: Config, key: str, default=None):
    """Resolve a config value, letting the artist override the global config."""
    return artist.config.get(key, getattr(config, key, default))


def extract_files(post: Post) -> List[dict]:
    """Return ``[{'name', 'path'}, ...]`` for a post's main file + attachments."""
    files = []
    if post.file and post.file.get('path'):
        files.append({'name': post.file.get('name', 'file'), 'path': post.file['path']})
    for att in (post.attachments or []):
        if att.get('path'):
            files.append({'name': att.get('name', 'attachment'), 'path': att['path']})
    return files
