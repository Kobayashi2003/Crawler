from pathlib import Path
from typing import List

from ..common.hotreload import plugin_hook
from ..common.naming import format_date, sanitize_component, sanitize_path
from .models import Artist, Post

# Hooks resolve per call, so edits hot-reload. No-ops by default.
_FORMAT_PLUGIN = 'src/plugins/format_plugin.py'


class Formatter:
    """Builds `download_dir / [group] / artist_folder / post_folder / file_name`.

    Every segment is sanitized for use as a Windows path component. Each naming
    level can be customised by a hot-reloaded plugin; `group` is a *location*,
    not a name, so it sits outside the plugin contract (see `artist_dir`).
    """

    @staticmethod
    def artist_dir(download_dir: str, artist: Artist, template: str, group: str = "") -> Path:
        """Where one artist's posts live.

        `group` mirrors the `data/artists/` tree (see `Storage.artist_groups`);
        empty -- the default, and what `artists.json` yields -- means the
        download root, leaving paths exactly as they were before grouping.
        """
        base = Path(download_dir)
        if group:
            base = base / sanitize_path(group)
        return base / Formatter.artist_folder(artist, template)

    @staticmethod
    @plugin_hook('format_artist_plugin', _FORMAT_PLUGIN)
    def artist_folder(artist: Artist, template: str) -> Path:
        # Values are sanitized *before* substitution: only a '/' written in the
        # template may create a directory. An alias like "hans.B / 藩滑るめる"
        # would otherwise split into two levels.
        raw = template.format(
            service=sanitize_component(artist.service),
            name=sanitize_component(artist.name),
            alias=sanitize_component(artist.alias or artist.name),
            user_id=sanitize_component(artist.user_id),
            last_date=(artist.last_date[:10] if artist.last_date else ""),
        )
        return Path(sanitize_path(raw))

    @staticmethod
    @plugin_hook('format_post_plugin', _FORMAT_PLUGIN)
    def post_folder(post: Post, template: str, date_format: str) -> str:
        raw = template.format(
            id=post.id,
            user=post.user,
            service=post.service,
            title=post.title,
            published=format_date(post.published, date_format),
        )
        return sanitize_component(raw)

    @staticmethod
    @plugin_hook('format_file_plugin', _FORMAT_PLUGIN)
    def format_file(name: str, idx: int, template: str) -> str:
        """Fields: `idx`, `name`."""
        out = template.format(idx=idx, name=name)
        if '.' not in out and '.' in name:
            out = f"{out}.{name.rsplit('.', 1)[-1]}"
        return sanitize_component(out)

    @staticmethod
    def file_names(names: List[str], template: str,
                   rename_images_only: bool, image_extensions: set) -> List[str]:
        """With `rename_images_only`, non-images keep their original name and
        images get a 0-based `{idx}`."""
        result = []
        image_index = 0
        for i, original in enumerate(names):
            is_image = Path(original).suffix.lower() in image_extensions
            if not rename_images_only or is_image:
                idx = image_index if (rename_images_only and is_image) else i
                if is_image:
                    image_index += 1
                result.append(Formatter.format_file(original, idx, template))
            else:
                result.append(sanitize_component(original))
        return result
