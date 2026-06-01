import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

import requests

from .config import Config
from .models import TrackInfo, BookletImage, AlbumInfo
from .browser_manager import create_driver
from .scraper import scrape_album, scrape_download_urls

_print_lock = threading.Lock()


def _print(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


def _retry_call(fn, label: str):
    """Retry fn() until it returns a truthy value. Only KeyboardInterrupt stops it."""
    attempt = 0
    while True:
        attempt += 1
        try:
            result = fn()
            if result:
                return result
            _print(f'Failed ({label}), retrying (attempt {attempt})...')
        except KeyboardInterrupt:
            raise
        except Exception as e:
            _print(f'Error ({label}) on attempt {attempt}: {e}, retrying...')


# --- public entry point ---

def download_album(config: Config, album_url: str):
    driver = create_driver(config)
    try:
        _print('Extracting album information...')
        album = scrape_album(driver, album_url, config)
        _print(f'Album: {album.name}')
        _print(f'Found {len(album.tracks)} tracks, {len(album.booklet_images)} booklet images')

        if config.download_booklet and album.booklet_images:
            _download_booklets(config, album)

        if album.tracks:
            _download_tracks(config, driver, album)
        else:
            _print('No tracks found!')
    finally:
        driver.quit()


# --- booklet download ---

def _download_booklets(config: Config, album: AlbumInfo):
    _print('\n=== Downloading Booklet Images ===')
    total = len(album.booklet_images)
    successful = 0

    def task(i: int, b: BookletImage) -> bool:
        _print(f'Downloading booklet image {i}/{total}: {b.filename}')
        filepath = _booklet_filepath(config.output_dir, album.name, b.filename)
        session = _new_session(config.user_agent)
        if config.retry:
            _retry_call(lambda: _save_file(b.url, filepath, session), f'booklet {b.filename}')
            return True
        return _save_file(b.url, filepath, session)

    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        futures = {executor.submit(task, i, b): b for i, b in enumerate(album.booklet_images, 1)}
        for future in as_completed(futures):
            try:
                if future.result():
                    successful += 1
            except Exception as e:
                _print(f'Booklet download error: {e}')

    _print(f'Downloaded {successful}/{total} booklet images')


# --- track download ---

def _download_tracks(config: Config, driver, album: AlbumInfo):
    _print('\n=== Downloading Music Tracks ===')
    total_tracks = len(album.tracks)

    cd_tracks: dict[int, list[TrackInfo]] = {}
    for t in album.tracks:
        cd_tracks.setdefault(t.cd_number, []).append(t)
    total_cds = len(cd_tracks)

    _print(f'Album has {total_cds} CD(s)')

    # Scraping (Selenium) is sequential; file downloads run in parallel.
    # We pipeline both: submit a download task as soon as its URL is scraped,
    # so downloads start immediately without waiting for all scraping to finish.
    successful = 0
    completed_count = 0
    futures: dict = {}

    def download_task(track: TrackInfo, file_url: str) -> bool:
        fmt = 'mp3' if '.mp3' in file_url.lower() else 'flac'
        safe_title = _sanitize(track.title)
        filename = f'{track.track_number:02d}. {safe_title}.{fmt}'
        filepath = _track_filepath(config.output_dir, album.name, track.cd_number, fmt, filename, total_cds)
        session = _new_session(config.user_agent)
        if config.retry:
            _retry_call(lambda: _save_file(file_url, filepath, session), f'track {filename}')
            return True
        return _save_file(file_url, filepath, session)

    def drain_completed():
        """Collect any futures that have already finished without blocking."""
        nonlocal successful, completed_count
        done = [f for f in list(futures) if f.done()]
        for f in done:
            completed_count += 1
            try:
                if f.result():
                    successful += 1
            except Exception as e:
                _print(f'Download error: {e}')
            _print(f'Progress: {completed_count} done')
            del futures[f]

    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        current = 0
        for cd_number in sorted(cd_tracks):
            for track in cd_tracks[cd_number]:
                current += 1
                label = (f'CD{track.cd_number}-{track.track_number:02d}. {track.title}'
                         if total_cds > 1 else f'{track.track_number:02d}. {track.title}')
                _print(f'Scraping {current}/{total_tracks}: {label}')
                try:
                    if config.retry:
                        while True:
                            try:
                                urls = scrape_download_urls(driver, track.song_page_url, config)
                                break  # page loaded successfully; empty list is a valid result
                            except KeyboardInterrupt:
                                raise
                            except Exception as e:
                                _print(f'Error getting URLs for track {current}: {e}, retrying...')
                    else:
                        urls = scrape_download_urls(driver, track.song_page_url, config)
                    for url in (urls or []):
                        f = executor.submit(download_task, track, url)
                        futures[f] = (track, url)
                    time.sleep(config.page_delay)
                except Exception as e:
                    _print(f'Error scraping track {current}: {e}')

                drain_completed()

        # Wait for remaining downloads to finish
        for f in as_completed(futures):
            completed_count += 1
            try:
                if f.result():
                    successful += 1
            except Exception as e:
                _print(f'Download error: {e}')
            _print(f'Progress: {completed_count} done')

    _print(f'\n=== Download Summary ===')
    _print(f'Successfully downloaded: {successful} file(s)')
    _print(f'Tracks processed: {total_tracks}')


# --- file I/O helpers ---

def _save_file(url: str, filepath: Path, session: requests.Session) -> bool:
    if filepath.exists():
        _print(f'Already exists: {filepath.name}')
        return True
    tmp = filepath.with_suffix(filepath.suffix + '.tmp')
    try:
        response = session.get(url, stream=True)
        response.raise_for_status()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        tmp.replace(filepath)
        size_mb = filepath.stat().st_size / (1024 * 1024)
        _print(f'Downloaded: {filepath.name} ({size_mb:.2f} MB)')
        return True
    except Exception as e:
        _print(f'Error downloading {url}: {e}')
        if tmp.exists():
            tmp.unlink()
        return False


def _new_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers['User-Agent'] = user_agent
    return session


def _sanitize(name: str) -> str:
    name = requests.utils.unquote(name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:200]


def _track_filepath(output_dir: str, album_name: str, cd_number: int,
                    fmt: str, filename: str, total_cds: int) -> Path:
    base = Path(output_dir) / _sanitize(album_name) / 'Music' / fmt.upper()
    return (base / f'CD{cd_number}' / filename) if total_cds > 1 else (base / filename)


def _booklet_filepath(output_dir: str, album_name: str, filename: str) -> Path:
    return Path(output_dir) / _sanitize(album_name) / 'Booklet' / _sanitize(filename)