"""One-off migration of kemono-downloader-v2 data into pawchive-downloader.

Pawchive reuses kemono's creator/post ids, so tracked artists, per-post
download state and templates carry over directly. This copies (never moves)
from a kemono-v2 checkout into this project:

  * data/artists.json and the data/artists/ folder tree  (url -> pawchive.st)
  * cache/*_posts.json                                   (done state preserved)
  * compatible fields of data/config.json

Profiles are intentionally not copied: kemono's `updated` timestamps don't map
to pawchive, so a fresh profile is fetched on the first `check` (which then
merges against the migrated posts, keeping every `done` flag).

Usage:
    python migrate_from_kemono.py [path-to-kemono-downloader-v2]

Default source is ../kemono-downloader-v2 relative to this file.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = HERE.parent / "kemono-downloader-v2"

# Fields kept when copying a Post (drops kemono-only `embed` / `shared_file`).
POST_FIELDS = ["id", "user", "service", "title", "content", "published",
               "added", "edited", "file", "attachments", "done", "failed_files"]

# Config keys pawchive understands (kemono proxy/clash keys are dropped).
CONFIG_FIELDS = ["cache_dir", "logs_dir", "temp_dir", "download_dir",
                 "global_timer", "global_filter", "retry_delay", "request_timeout",
                 "max_concurrent_artists", "max_concurrent_posts", "max_concurrent_files",
                 "date_format", "artist_folder_template", "post_folder_template",
                 "file_template", "save_content", "save_empty_posts",
                 "rename_images_only", "image_extensions"]


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _fix_artist(a: dict) -> dict:
    """Rewrite the creator url to point at pawchive; leave everything else."""
    a = dict(a)
    service, user_id = a.get("service"), a.get("user_id")
    if service and user_id:
        a["url"] = f"https://pawchive.st/{service}/user/{user_id}"
    return a


def _fix_artists_content(content):
    if isinstance(content, list):
        return [_fix_artist(x) for x in content if isinstance(x, dict)]
    if isinstance(content, dict):
        return _fix_artist(content)
    return content


def migrate_artists(src: Path, dst: Path) -> int:
    count = 0

    src_file = src / "data" / "artists.json"
    if src_file.exists():
        artists = _fix_artists_content(_read_json(src_file))
        _write_json(dst / "data" / "artists.json", artists)
        count += len(artists)
        print(f"  artists.json: {len(artists)} creators")

    src_dir = src / "data" / "artists"
    if src_dir.is_dir():
        sub = 0
        for path in sorted(src_dir.rglob("*.json")):
            rel = path.relative_to(src_dir)
            content = _fix_artists_content(_read_json(path))
            _write_json(dst / "data" / "artists" / rel, content)
            sub += len(content) if isinstance(content, list) else 1
        if sub:
            print(f"  data/artists/ tree: {sub} creators")
        count += sub

    return count


def migrate_cache(src: Path, dst: Path) -> int:
    src_cache = src / "cache"
    if not src_cache.is_dir():
        return 0
    files = sorted(src_cache.glob("*_posts.json"))
    posts_total = 0
    for path in files:
        try:
            raw = _read_json(path)
        except Exception as e:
            print(f"  ! skip {path.name}: {e}")
            continue
        cleaned = [{k: p.get(k) for k in POST_FIELDS} for p in raw]
        _write_json(dst / "cache" / path.name, cleaned)
        posts_total += len(cleaned)
    done = sum(
        1
        for path in (dst / "cache").glob("*_posts.json")
        for p in _read_json(path)
        if p.get("done")
    )
    print(f"  cache: {len(files)} creators, {posts_total} posts ({done} already done)")
    return len(files)


def migrate_config(src: Path, dst: Path) -> bool:
    src_file = src / "data" / "config.json"
    if not src_file.exists():
        return False
    src_cfg = _read_json(src_file)
    if not src_cfg:
        return False
    cfg = {k: src_cfg[k] for k in CONFIG_FIELDS if k in src_cfg}
    _write_json(dst / "data" / "config.json", cfg)
    print(f"  config.json: {len(cfg)} settings migrated")
    if src_cfg.get("use_proxy"):
        print("  ! kemono used a Clash proxy pool; set `proxy` manually in "
              "data/config.json if you still need one.")
    return True


def main():
    src = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.is_dir():
        print(f"Source not found: {src}")
        sys.exit(1)
    if src.resolve() == HERE:
        print("Source and destination are the same directory.")
        sys.exit(1)

    print(f"Migrating from: {src}")
    print(f"            to: {HERE}\n")

    artists = migrate_artists(src, HERE)
    caches = migrate_cache(src, HERE)
    migrate_config(src, HERE)

    print(f"\nDone. {artists} creators and {caches} caches migrated.")
    print("Run `python main.py` and `check-all` to resume from where kemono left off.")


if __name__ == "__main__":
    main()
