#!/usr/bin/env python3
"""
Rename album tracks by converting track names between languages using a VGMDB tracklist.

Usage:
    python rename_tracks.py <album_dir> <vgmdb_url> --from en --to ja
    python rename_tracks.py <album_dir> <vgmdb_url> --from en --to ja --dry-run
    python rename_tracks.py <album_dir> <vgmdb_url> --from en --to ja --browser chrome

The album directory should contain audio files named like:
    01. Song Title.mp3
    02. Another Song.flac
Or for multi-CD albums, subdirectories:
    CD1/01. Song Title.mp3
    CD2/01. First Track CD2.mp3
"""

import re
import sys
import time
import argparse
from pathlib import Path

from selenium.webdriver.common.by import By

from src.browser_manager import create_driver
from src.config import Config

# Maps user-supplied language codes to VGMDB span class names
LANG_ALIASES = {
    'en': 'en', 'english': 'en',
    'ja': 'ja', 'jp': 'ja', 'japanese': 'ja',
    'ro': 'ro', 'romaji': 'ro',
}

AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.wav', '.m4a', '.aac'}


# ---------------------------------------------------------------------------
# VGMDB scraping
# ---------------------------------------------------------------------------

def scrape_tracklist(driver, url: str) -> dict:
    """
    Scrape a VGMDB album page and return all track names in every available language.

    Returns:
        {
            disc_number (int): {
                track_number (int): {
                    'en': 'English Name',
                    'ja': '日本語名',
                    'ro': 'Romaji Name',
                    ...
                }
            }
        }
    """
    print(f'Loading {url} ...')
    driver.get(url)
    time.sleep(3)

    # All track name data is present in the DOM even when hidden by JS tabs.
    # Extract it via JavaScript to avoid wrestling with display:none elements.
    data = driver.execute_script("""
        var result = {};
        var discNum = 1;

        var table = document.querySelector('#tracklist table.tl, table.tl');
        if (!table) return result;

        var rows = table.querySelectorAll('tr');
        rows.forEach(function(row) {
            // Disc header row
            var discHead = row.querySelector('td.subgroup, td[colspan]');
            if (discHead) {
                var m = discHead.textContent.match(/Disc\\s*(\\d+)/i);
                if (m) discNum = parseInt(m[1]);
                return;
            }

            // Track row
            var trackCell = row.querySelector('td.track');
            if (!trackCell) return;

            var trackNum = parseInt(trackCell.textContent.trim());
            if (isNaN(trackNum)) return;

            // Name cell — collect all language spans
            var nameCell = row.querySelector('td.tleft, td:nth-child(3)');
            if (!nameCell) return;

            var names = {};
            var spans = nameCell.querySelectorAll('span[class]');
            if (spans.length > 0) {
                spans.forEach(function(span) {
                    var lang = span.className.trim().split(/\\s+/)[0];
                    var text = span.textContent.trim();
                    if (text) names[lang] = text;
                });
            } else {
                // Fallback: plain text, no language spans
                var text = nameCell.textContent.trim();
                if (text) names['en'] = text;
            }

            if (!result[discNum]) result[discNum] = {};
            result[discNum][trackNum] = names;
        });

        return result;
    """)

    if not data:
        raise RuntimeError(
            'No tracklist data found. Make sure the URL is a valid VGMDB album page.'
        )

    # Convert JS object keys (strings) to int
    result = {}
    for disc_str, tracks in data.items():
        disc = int(disc_str)
        result[disc] = {}
        for track_str, names in tracks.items():
            result[disc][int(track_str)] = names

    return result


def available_languages(tracklist: dict) -> set:
    langs = set()
    for tracks in tracklist.values():
        for names in tracks.values():
            langs.update(names.keys())
    return langs


# ---------------------------------------------------------------------------
# Album directory scanning
# ---------------------------------------------------------------------------

def scan_album(album_dir: Path) -> dict:
    """
    Scan the album directory for audio files and return them indexed by (disc, track).

    Returns:
        { (disc_number, track_number): Path }

    Recognizes:
        - Flat layout:        album/01. Title.mp3
        - Multi-CD layout:    album/CD1/01. Title.mp3
    """
    files = {}
    track_re = re.compile(r'^(\d{1,3})\.\s+(.+)$')

    def add_file(path: Path, disc: int):
        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            return
        m = track_re.match(path.stem)
        if not m:
            return
        track_num = int(m.group(1))
        files[(disc, track_num)] = path

    # Check for CD subdirectories
    cd_dirs = sorted(album_dir.glob('CD*'))
    cd_dirs = [d for d in cd_dirs if d.is_dir() and re.match(r'CD\d+$', d.name, re.IGNORECASE)]

    if cd_dirs:
        for cd_dir in cd_dirs:
            disc = int(re.search(r'\d+', cd_dir.name).group())
            for f in sorted(cd_dir.iterdir()):
                add_file(f, disc)
    else:
        for f in sorted(album_dir.iterdir()):
            add_file(f, disc=1)

    return files


# ---------------------------------------------------------------------------
# Renaming logic
# ---------------------------------------------------------------------------

def build_rename_plan(album_files: dict, tracklist: dict, from_lang: str, to_lang: str) -> list:
    """
    Returns a list of (old_path, new_path) tuples representing planned renames.
    """
    plan = []
    warnings = []

    for (disc, track), path in sorted(album_files.items()):
        disc_data = tracklist.get(disc)
        if disc_data is None:
            warnings.append(f'  [WARN] Disc {disc} not found in VGMDB tracklist — skipping {path.name}')
            continue

        track_data = disc_data.get(track)
        if track_data is None:
            warnings.append(f'  [WARN] Track {track} (disc {disc}) not in VGMDB tracklist — skipping {path.name}')
            continue

        if from_lang not in track_data:
            warnings.append(
                f'  [WARN] Language "{from_lang}" not available for disc {disc} track {track} '
                f'(available: {list(track_data.keys())}) — skipping {path.name}'
            )
            continue

        if to_lang not in track_data:
            warnings.append(
                f'  [WARN] Language "{to_lang}" not available for disc {disc} track {track} '
                f'(available: {list(track_data.keys())}) — skipping {path.name}'
            )
            continue

        new_stem = f'{track:02d}. {track_data[to_lang]}'
        new_name = sanitize_filename(new_stem) + path.suffix
        new_path = path.parent / new_name

        if path.name == new_name:
            continue  # Already correct name

        plan.append((path, new_path))

    for w in warnings:
        print(w)

    return plan


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:200]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Rename album tracks using VGMDB language tracklist'
    )
    parser.add_argument('album_dir', help='Path to the album directory')
    parser.add_argument('vgmdb_url', help='VGMDB album URL (e.g. https://vgmdb.net/album/23630)')
    parser.add_argument('--from', dest='from_lang', default='en',
                        help='Source language (en/ja/ro, default: en)')
    parser.add_argument('--to', dest='to_lang', default='ja',
                        help='Target language (en/ja/ro, default: ja)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview renames without making any changes')
    parser.add_argument('--browser', choices=['chrome', 'edge', 'firefox', 'auto'],
                        default='auto', help='Browser to use (default: auto)')
    parser.add_argument('--headless', action='store_true',
                        help='Run browser in headless mode')
    args = parser.parse_args()

    album_dir = Path(args.album_dir)
    if not album_dir.is_dir():
        print(f'Error: "{album_dir}" is not a valid directory')
        sys.exit(1)

    from_lang = LANG_ALIASES.get(args.from_lang.lower())
    to_lang = LANG_ALIASES.get(args.to_lang.lower())
    if not from_lang:
        print(f'Error: unknown source language "{args.from_lang}". Use en, ja, or ro.')
        sys.exit(1)
    if not to_lang:
        print(f'Error: unknown target language "{args.to_lang}". Use en, ja, or ro.')
        sys.exit(1)
    if from_lang == to_lang:
        print('Source and target language are the same — nothing to do.')
        sys.exit(0)

    # Scan album directory
    album_files = scan_album(album_dir)
    if not album_files:
        print(f'No audio files found in "{album_dir}"')
        sys.exit(1)
    print(f'Found {len(album_files)} audio file(s) in "{album_dir}"')

    # Scrape VGMDB
    config = Config(browser=args.browser, headless=args.headless)
    driver = create_driver(config)
    try:
        tracklist = scrape_tracklist(driver, args.vgmdb_url)
    finally:
        driver.quit()

    total_discs = len(tracklist)
    total_tracks = sum(len(t) for t in tracklist.values())
    print(f'Scraped {total_tracks} track(s) across {total_discs} disc(s) from VGMDB')

    langs = available_languages(tracklist)
    print(f'Available languages: {sorted(langs)}')
    if from_lang not in langs:
        print(f'Error: source language "{from_lang}" not found in tracklist.')
        sys.exit(1)
    if to_lang not in langs:
        print(f'Error: target language "{to_lang}" not found in tracklist.')
        sys.exit(1)

    # Build and display rename plan
    plan = build_rename_plan(album_files, tracklist, from_lang, to_lang)

    if not plan:
        print('Nothing to rename — all files already match the target language names.')
        sys.exit(0)

    print(f'\n{"[DRY RUN] " if args.dry_run else ""}Rename plan ({len(plan)} file(s)):')
    for old_path, new_path in plan:
        print(f'  {old_path.name}')
        print(f'    -> {new_path.name}')

    if args.dry_run:
        print('\nDry run complete. No files were renamed.')
        sys.exit(0)

    # Execute renames
    print()
    errors = 0
    for old_path, new_path in plan:
        try:
            if new_path.exists():
                print(f'  [SKIP] Target already exists: {new_path.name}')
                continue
            old_path.rename(new_path)
            print(f'  Renamed: {old_path.name} -> {new_path.name}')
        except Exception as e:
            print(f'  [ERROR] Failed to rename {old_path.name}: {e}')
            errors += 1

    renamed = len(plan) - errors
    print(f'\nDone. Renamed {renamed}/{len(plan)} file(s).')
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
