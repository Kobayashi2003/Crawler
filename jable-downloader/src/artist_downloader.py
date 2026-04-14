#!/usr/bin/env python3

import os
import re
import sys
import time
import argparse

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from .video_downloader import download_video
from .core.browser import create_driver
from .utils.helpers import sanitize_filename, is_artist_url, extract_video_id
from .utils.config import get_last_template, save_template
from .utils.logger import Logger

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

        parent = tabs[0].find_element(By.XPATH, '..')
        if 'active' in (parent.get_attribute('class') or ''):
            return

        soup_before = BeautifulSoup(driver.page_source, 'html.parser')
        first_el = soup_before.select_one('.video-img-box h6.title a')
        old_title = first_el.get_text(strip=True) if first_el else None

        driver.execute_script('arguments[0].click();', tabs[0])

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
    artist_name = url.rstrip('/').split('/')[-1]

    try:
        url = url.rstrip('/') + '/'
        driver.get(url)
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        h2 = soup.select_one('h2')
        if h2:
            name = h2.get_text(strip=True)
            if name:
                artist_name = name

        if sort_by:
            apply_sort(driver, sort_by)

        total_pages = get_total_pages(driver.page_source)
        print(f'Found {total_pages} page(s)')

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

    return all_videos, artist_name


def _download_one(index, total, video, folder_path, template, artist_name, log):
    video_id = extract_video_id(video['url'])
    folder_name = template.replace('{video_id}', video_id)
    folder_name = folder_name.replace('{title}', video['title'])
    folder_name = folder_name.replace('{artist}', artist_name)
    folder_name = sanitize_filename(folder_name)

    log.video_start(index, total, video['title'])
    try:
        result = download_video(video['url'], folder_path, folder_name=folder_name)
        if result == 'skipped':
            log.video_done(index, total, Logger.STATUS_SKIP, folder_name)
            log.record(index, video_id, video['title'], Logger.STATUS_SKIP)
        else:
            log.video_done(index, total, Logger.STATUS_OK)
            log.record(index, video_id, video['title'], Logger.STATUS_OK)
    except Exception as e:
        log.video_done(index, total, Logger.STATUS_FAIL, str(e))
        log.record(index, video_id, video['title'], Logger.STATUS_FAIL, str(e))


def main():
    parser = argparse.ArgumentParser(
        description='Download all videos from a Jable artist page'
    )
    parser.add_argument('url', help='Artist page URL (e.g. https://jable.tv/models/xxx/)')
    parser.add_argument('-p', '--path', default=None, help='Download folder path')
    parser.add_argument(
        '--sort', choices=list(SORT_MAP.keys()), default=None,
        help='Sort order: best, latest, views, favorites'
    )
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of videos')
    parser.add_argument('--template', default=None,
                        help='Naming template: {video_id}, {title}, {artist}')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation')

    args = parser.parse_args()
    log = Logger()

    if not is_artist_url(args.url):
        print(f'Invalid Jable artist URL: {args.url}')
        sys.exit(1)

    template = args.template or get_last_template()
    save_template(template)

    folder_path = args.path or os.getcwd()

    log.header('Jable Artist Downloader')
    log.info(f'  URL:      {args.url}')
    if args.sort:
        log.info(f'  Sort:     {SORT_MAP[args.sort]}')
    if args.limit:
        log.info(f'  Limit:    {args.limit}')
    log.info(f'  Template: {template}')
    log.info(f'  Output:   {folder_path}')
    print()

    videos, artist_name = collect_all_videos(args.url, sort_by=args.sort, limit=args.limit)

    if not videos:
        print('No videos found.')
        sys.exit(0)

    log.header(f'Found {len(videos)} video(s)')
    for i, v in enumerate(videos, 1):
        print(f'  {i:3d}. {v["title"]}')
        print(f'       {v["url"]}')

    if not args.no_confirm:
        print()
        confirm = input('Start downloading? [y/N]: ').strip().lower()
        if confirm != 'y':
            print('Cancelled.')
            sys.exit(0)

    total = len(videos)
    for i, v in enumerate(videos, 1):
        _download_one(i, total, v, folder_path, template, artist_name, log)

    log.print_summary()

    # Retry loop for failed downloads
    while log.get_failed():
        failed = log.get_failed()
        print()
        retry = input(f'{len(failed)} video(s) failed. Retry? [y/N]: ').strip().lower()
        if retry != 'y':
            break

        failed_ids = {r['video_id'] for r in failed}
        retry_videos = [v for v in videos if extract_video_id(v['url']) in failed_ids]
        log.clear_failed()

        retry_total = len(retry_videos)
        for i, v in enumerate(retry_videos, 1):
            _download_one(i, retry_total, v, folder_path, template, artist_name, log)

        log.print_summary()


if __name__ == '__main__':
    main()
