#!/usr/bin/env python3
"""Project Sekai character image downloader.

Downloads character images (profiles, stamps, SD characters, 3D models, comics
and cards) from pjsekai.gamedbs.jp. Site: https://pjsekai.gamedbs.jp
"""

import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

BASE_URL = "https://pjsekai.gamedbs.jp"

# (subdir, filename_prefix, url regex) for the image sections on a character page
SECTIONS = [
    ("profile", "profile", r"/image/chara/img/"),
    ("stamps", "stamp", r"/image/chara/stp/"),
    ("sd_characters", "sd", r"/image/chara/sdc/"),
    ("3d_models", "3d_model", r"/image/chara/3d[cs]/"),
    ("comics", "comic", r"/image/chara/cm1/"),
]


# ---- helpers ----

def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or "_"


def create_session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def download_image(session, img_url, save_path):
    """Download a single image, skipping if it already exists."""
    if save_path.exists():
        return False
    try:
        resp = session.get(img_url, timeout=30)
        resp.raise_for_status()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(resp.content)
        print(f"  ✓ {save_path.name}")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def collect_urls(soup, url_re):
    """De-duplicated image URLs matching url_re from img[src], img[data-src] and a[href]."""
    pattern = re.compile(url_re)
    seen, urls = set(), []
    for img in soup.find_all("img"):
        for attr in ("src", "data-src"):
            u = img.get(attr)
            if u and pattern.search(u) and u not in seen:
                seen.add(u)
                urls.append(u)
    for a in soup.find_all("a", href=True):
        u = a["href"]
        if pattern.search(u) and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


# ---- scraping / download ----

def download_section(session, soup, char_dir, subdir, prefix, url_re, delay):
    urls = collect_urls(soup, url_re)
    if not urls:
        return 0
    print(f"  {subdir}:")
    total = 0
    for i, u in enumerate(urls, 1):
        full_url = urljoin(BASE_URL, u)
        ext = Path(urlparse(full_url).path).suffix
        if download_image(session, full_url, char_dir / subdir / f"{prefix}{i}{ext}"):
            total += 1
        time.sleep(delay)
    return total


def get_all_characters(session):
    print("Fetching character list...")
    try:
        resp = session.get(f"{BASE_URL}/", timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to get character list: {e}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    ids = set()
    for link in soup.find_all("a", href=True):
        match = re.search(r"/chara/show/(\d+)$", urljoin(BASE_URL, link["href"]))
        if match:
            ids.add(match.group(1))

    characters = sorted(ids, key=int)
    print(f"Found {len(characters)} characters\n")
    return characters


def get_character_name(soup, char_id):
    title = soup.find("h3", class_="uk-heading-line")
    if title:
        match = re.search(r"】\s*(.+?)\s+(?:情報|メンバー)", title.get_text(strip=True))
        if match:
            return sanitize_filename(match.group(1))
    return f"Character_{char_id}"


def download_cards(session, soup, char_dir, char_id, delay):
    card_links = soup.find_all("a", href=re.compile(rf"/chara/show/{char_id}/\d+"))
    if not card_links:
        return 0
    print(f"  cards ({len(card_links)} found):")
    total = 0
    for link in card_links:
        card_url = urljoin(BASE_URL, link["href"])
        card_name = sanitize_filename(link.get_text(strip=True) or "Unknown")
        total += download_card_images(session, card_url, char_dir, card_name, delay)
        time.sleep(1)
    return total


def download_card_images(session, card_url, char_dir, card_name, delay):
    try:
        resp = session.get(card_url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return 0

    soup = BeautifulSoup(resp.content, "html.parser")
    downloaded = 0

    # (href regex, subdir, suffixes for 特訓前 / 特訓後 / neither)
    groups = [
        (r"/image/chara/member/", "cards", ("_before", "_after", "")),
        (r"/image/chara/member_trm/", "cards_trimmed",
         ("_before_trimmed", "_after_trimmed", "_trimmed")),
    ]
    for href_re, subdir, (before, after, plain) in groups:
        for link in soup.find_all("a", href=re.compile(href_re)):
            img_url = urljoin(BASE_URL, link["href"])
            ext = Path(urlparse(img_url).path).suffix
            text = link.get("data-caption", "") + link.get_text()
            suffix = before if "特訓前" in text else after if "特訓後" in text else plain
            if download_image(session, img_url, char_dir / subdir / f"{card_name}{suffix}{ext}"):
                downloaded += 1
            time.sleep(delay)
    return downloaded


def download_character(session, char_id, output_dir, delay=0.3):
    char_url = f"{BASE_URL}/chara/show/{char_id}"
    try:
        resp = session.get(char_url, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        print(f"[{char_id}] HTTP {code}\n")
        return 0
    except Exception as e:
        print(f"[{char_id}] Failed: {e}\n")
        return 0

    soup = BeautifulSoup(resp.content, "html.parser")
    char_name = get_character_name(soup, char_id)
    char_dir = Path(output_dir) / char_name

    if char_dir.exists():
        print(f"[{char_id}] {char_name} - already downloaded, skipping")
        return 0

    print(f"[{char_id}] {char_name}")
    char_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for subdir, prefix, url_re in SECTIONS:
        total += download_section(session, soup, char_dir, subdir, prefix, url_re, delay)
    total += download_cards(session, soup, char_dir, char_id, delay)

    print(f"  Total: {total} images\n")
    return total


def download_all(output_dir="downloads", delay=0.3):
    print("=" * 60)
    print("Project Sekai Character Image Downloader")
    print("=" * 60 + "\n")

    session = create_session()
    characters = get_all_characters(session)
    if not characters:
        print("No characters found")
        return

    total_images = 0
    for char_id in characters:
        total_images += download_character(session, char_id, output_dir, delay)
        time.sleep(2)

    print("=" * 60)
    print(f"Completed! Total images: {total_images}")
    print(f"Location: {Path(output_dir).absolute()}")
    print("=" * 60)


# ---- CLI ----

def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Project Sekai character image downloader")
    parser.add_argument("-o", "--output", default="downloads", help="Output directory")
    parser.add_argument("--char", action="append", default=None,
                        help="Download a specific character id (repeatable). Default: all characters")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between image downloads (s)")
    args = parser.parse_args(argv)

    if args.char:
        session = create_session()
        for char_id in args.char:
            download_character(session, char_id, args.output, args.delay)
    else:
        download_all(output_dir=args.output, delay=args.delay)


if __name__ == "__main__":
    main()
