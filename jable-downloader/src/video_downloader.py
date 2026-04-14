import os
import time

from bs4 import BeautifulSoup

from .utils.config import create_session
from .core.browser import create_driver
from .core.m3u8_downloader import parse_m3u8, fetch_m3u8, download_segments, merge_segments
from .core.encoder import ffmpeg_encode
from .utils.helpers import extract_video_id


def _scrape_video_page(url):
    driver = create_driver()
    try:
        driver.get(url=url)
        page_source = driver.page_source
    finally:
        driver.quit()

    soup = BeautifulSoup(page_source, 'html.parser')

    cover_meta = soup.find('meta', property='og:image')
    cover_url = cover_meta['content'] if cover_meta else None

    m3u8_url = parse_m3u8(page_source)

    return cover_url, m3u8_url


def _download_cover(cover_url, folder_path, session):
    if not cover_url:
        return

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    cover_name = cover_url.split('/')[-1]
    cover_path = os.path.join(folder_path, cover_name)
    if os.path.exists(cover_path):
        return

    for attempt in range(3):
        try:
            resp = session.get(cover_url, timeout=30)
            resp.raise_for_status()
            with open(cover_path, 'wb') as f:
                f.write(resp.content)
            return
        except Exception as e:
            if attempt < 2:
                print(f'  [!] Cover retry ({attempt + 1}/3): {e}')
                time.sleep(2)
            else:
                print(f'  [!] Cover failed: {e}')


def download_video(url, folder_path, folder_name=None):
    video_id = extract_video_id(url)
    folder_name = folder_name or video_id
    video_folder = os.path.join(folder_path, folder_name)

    ts_folder = os.path.join(video_folder, 'ts')
    video_file = os.path.join(video_folder, video_id + '.mp4')
    encode_file = os.path.join(video_folder, 'f_' + video_id + '.mp4')

    if os.path.exists(video_file):
        return 'skipped'

    session = create_session()

    # Single page load for both cover and m3u8
    cover_url, m3u8_url = _scrape_video_page(url)

    if not m3u8_url:
        raise RuntimeError('m3u8 URL not found on page')

    _download_cover(cover_url, video_folder, session)

    ts_urls, cipher = fetch_m3u8(m3u8_url, video_folder, video_id, session=session)

    fail_count = download_segments(ts_urls, cipher, ts_folder, session=session)
    if fail_count:
        raise RuntimeError(f'{fail_count} segment(s) failed after retries')

    print('  Merging...', end=' ', flush=True)
    merge_segments(ts_urls, ts_folder, video_file)
    print('done.')

    print('  Encoding...', end=' ', flush=True)
    if ffmpeg_encode(video_file, encode_file):
        os.remove(video_file)
        os.rename(encode_file, video_file)
        print('done.')
    else:
        if os.path.exists(encode_file):
            os.remove(encode_file)
        print('failed (raw file kept).')

    return 'ok'
