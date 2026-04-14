#!/usr/bin/env python3

import os
import re
import sys
import time
import argparse

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from .downloader import downloadVideo
from .browser import create_driver
from .utils import sanitize_filename, is_model_url
from .config import get_last_template, save_template

SORT_MAP = {
    'best': '近期最佳',
    'latest': '最近更新',
    'views': '最多觀看',
    'favorites': '最高收藏',
}


def parse_videos_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    videos = []
    seen = set()

    for card in soup.select('.video-img-box'):
        link = card.select_one('h6.title a')
        if not link:
            link = card.select_one('a[href*="/videos/"]')
        if not link:
            continue

        href = link.get('href', '')
        if not re.match(r'https?://jable\.tv/videos/[^/]+/', href):
            continue
        if href in seen:
            continue
        seen.add(href)

        title_tag = card.select_one('h6.title a')
        title = title_tag.get_text(strip=True) if title_tag else href.rstrip('/').split('/')[-1]
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
        if not tabs:
            print(f'Warning: Sort tab "{sort_text}" not found.')
            return

        # Check if this tab is already active
        parent = tabs[0].find_element(By.XPATH, '..')
        if 'active' in (parent.get_attribute('class') or ''):
            return

        # Capture first video before click to detect content change
        soup_before = BeautifulSoup(driver.page_source, 'html.parser')
        first_el = soup_before.select_one('.video-img-box h6.title a')
        old_title = first_el.get_text(strip=True) if first_el else None

        # Use JS click for reliability in headless mode
        driver.execute_script('arguments[0].click();', tabs[0])

        # Wait for content to refresh (up to 10 seconds)
        for _ in range(20):
            time.sleep(0.5)
            soup_after = BeautifulSoup(driver.page_source, 'html.parser')
            first_after = soup_after.select_one('.video-img-box h6.title a')
            new_title = first_after.get_text(strip=True) if first_after else None
            if new_title and new_title != old_title:
                break
        else:
            time.sleep(2)
    except Exception as e:
        print(f'Warning: Could not apply sort "{sort_text}": {e}')


def collect_all_videos(url, sort_by=None, limit=None):
    driver = create_driver()
    all_videos = []
    actress_name = url.rstrip('/').split('/')[-1]

    try:
        url = url.rstrip('/') + '/'
        driver.get(url)
        time.sleep(3)

        # Extract actress display name from page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        h2 = soup.select_one('h2')
        if h2:
            name = h2.get_text(strip=True)
            if name:
                actress_name = name

        if sort_by:
            apply_sort(driver, sort_by)

        # Read total pages AFTER sort is applied
        total_pages = get_total_pages(driver.page_source)
        print(f'Found {total_pages} page(s)')

        # Collect page 1 (already loaded and sorted)
        videos = parse_videos_from_html(driver.page_source)
        all_videos.extend(videos)
        print(f'  Page 1: {len(videos)} video(s)')

        if limit and len(all_videos) >= limit:
            all_videos = all_videos[:limit]
        else:
            for page in range(2, total_pages + 1):
                page_url = f'{url}{page}/'
                driver.get(page_url)
                time.sleep(3)
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

    return all_videos, actress_name


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
    parser.add_argument('--template', default=None,
                        help='Naming template. Variables: {video_id}, {title}, {actress}')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    if not is_model_url(args.url):
        print(f'Invalid Jable model URL: {args.url}')
        sys.exit(1)

    # Use saved template if not specified
    template = args.template or get_last_template()
    save_template(template)

    folder_path = args.path or os.getcwd()

    print(f'Collecting videos from: {args.url}')
    if args.sort:
        print(f'Sort order: {SORT_MAP[args.sort]}')
    if args.limit:
        print(f'Limit: {args.limit} video(s)')
    print(f'Template: {template}')
    print()

    videos, actress_name = collect_all_videos(args.url, sort_by=args.sort, limit=args.limit)

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
        video_id = v['url'].rstrip('/').split('/')[-1]
        folder_name = template.replace('{video_id}', video_id)
        folder_name = folder_name.replace('{title}', v['title'])
        folder_name = folder_name.replace('{actress}', actress_name)
        folder_name = sanitize_filename(folder_name)

        print(f'\n[{i}/{len(videos)}] {v["title"]}')
        try:
            downloadVideo(v['url'], folder_path, folder_name=folder_name)
            print('  Done.')
        except Exception as e:
            print(f'  Error: {e}')

    print(f'\nAll downloads completed. ({len(videos)} video(s))')


if __name__ == '__main__':
    main()
