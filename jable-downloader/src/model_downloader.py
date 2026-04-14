#!/usr/bin/env python3

import os
import re
import sys
import time
import argparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from .downloader import downloadVideo

SORT_MAP = {
    'best': '近期最佳',
    'latest': '最近更新',
    'views': '最多觀看',
    'favorites': '最高收藏',
}


def create_driver():
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    options.add_argument('--headless')
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 6.1; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36'
    )
    return webdriver.Chrome(options=options)


def is_model_url(url):
    return bool(re.match(r'https?://jable\.tv/models/[^/]+/?$', url))


def parse_videos_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    videos = []
    seen = set()

    for a in soup.select('a[href*="/videos/"]'):
        href = a.get('href', '')
        if not re.match(r'https?://jable\.tv/videos/[^/]+/', href):
            continue
        if href in seen:
            continue
        seen.add(href)

        h6 = a.find('h6')
        title = h6.get_text(strip=True) if h6 else href.rstrip('/').split('/')[-1]
        videos.append({'title': title, 'url': href})

    return videos


def get_total_pages(html):
    soup = BeautifulSoup(html, 'html.parser')
    pages = set()
    for a in soup.select('ul.pagination a'):
        href = a.get('href', '')
        match = re.search(r'/(\d+)/?$', href)
        if match:
            pages.add(int(match.group(1)))
    return max(pages) if pages else 1


def apply_sort(driver, sort_key):
    sort_text = SORT_MAP.get(sort_key)
    if not sort_text:
        return
    try:
        tabs = driver.find_elements(By.LINK_TEXT, sort_text)
        if tabs:
            tabs[0].click()
            time.sleep(2)
        else:
            all_links = driver.find_elements(By.TAG_NAME, 'a')
            for link in all_links:
                if sort_text in link.text:
                    link.click()
                    time.sleep(2)
                    return
            print(f'Warning: Sort tab "{sort_text}" not found.')
    except Exception as e:
        print(f'Warning: Could not apply sort "{sort_text}": {e}')


def collect_all_videos(url, sort_by=None, limit=None):
    driver = create_driver()
    all_videos = []

    try:
        url = url.rstrip('/') + '/'
        driver.get(url)
        time.sleep(3)

        if sort_by:
            apply_sort(driver, sort_by)

        total_pages = get_total_pages(driver.page_source)
        print(f'Found {total_pages} page(s)')

        for page in range(1, total_pages + 1):
            if page > 1:
                page_url = f'{url}{page}/'
                driver.get(page_url)
                time.sleep(2)
                if sort_by:
                    apply_sort(driver, sort_by)

            videos = parse_videos_from_html(driver.page_source)
            all_videos.extend(videos)
            print(f'  Page {page}: {len(videos)} video(s)')

            if limit and len(all_videos) >= limit:
                all_videos = all_videos[:limit]
                break
    finally:
        driver.quit()

    return all_videos


def main():
    parser = argparse.ArgumentParser(
        description='Download all videos from a Jable model page'
    )
    parser.add_argument('url', help='Model page URL (e.g. https://jable.tv/models/hikaru-emo/)')
    parser.add_argument('-p', '--path', default=None, help='Download folder path')
    parser.add_argument(
        '--sort', choices=list(SORT_MAP.keys()), default=None,
        help='Sort order: best, latest, views, favorites'
    )
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of videos to download')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    if not is_model_url(args.url):
        print(f'Invalid Jable model URL: {args.url}')
        sys.exit(1)

    folder_path = args.path or os.getcwd()

    print(f'Collecting videos from: {args.url}')
    if args.sort:
        print(f'Sort order: {SORT_MAP[args.sort]}')
    if args.limit:
        print(f'Limit: {args.limit} video(s)')
    print()

    videos = collect_all_videos(args.url, sort_by=args.sort, limit=args.limit)

    if not videos:
        print('No videos found.')
        sys.exit(0)

    print(f'\n{"=" * 60}')
    print(f'Found {len(videos)} video(s):')
    print(f'{"=" * 60}')
    for i, v in enumerate(videos, 1):
        print(f'  {i:3d}. {v["title"]}')
        print(f'       {v["url"]}')
    print(f'{"=" * 60}\n')

    if not args.no_confirm:
        confirm = input('Start downloading? [y/N]: ').strip().lower()
        if confirm != 'y':
            print('Cancelled.')
            sys.exit(0)

    for i, v in enumerate(videos, 1):
        print(f'\n[{i}/{len(videos)}] {v["title"]}')
        try:
            downloadVideo(v['url'], folder_path)
            print('  Done.')
        except Exception as e:
            print(f'  Error: {e}')

    print(f'\nAll downloads completed. ({len(videos)} video(s))')


if __name__ == '__main__':
    main()
