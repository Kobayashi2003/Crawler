import os
import re
import threading
import tqdm

from concurrent.futures import ThreadPoolExecutor

import m3u8
from Crypto.Cipher import AES

from ..utils.config import create_session

MAX_WORKERS = 32
MAX_RETRIES = 5
TS_TIMEOUT = 30


def parse_m3u8(page_source):
    urls = re.findall(r"https://[^\s\"']+\.m3u8", page_source)
    return urls[0] if urls else None


def fetch_m3u8(m3u8_url, folder_path, video_id, session=None):
    _session = session or create_session()

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    m3u8_file = os.path.join(folder_path, f'{video_id}.m3u8')

    resp = _session.get(m3u8_url, timeout=30)
    resp.raise_for_status()
    with open(m3u8_file, 'wb') as f:
        f.write(resp.content)

    m3u8_obj = m3u8.load(m3u8_file)
    base_url = '/'.join(m3u8_url.split('/')[:-1])

    cipher = None
    for key in m3u8_obj.keys:
        if key:
            key_url = base_url + '/' + key.uri
            key_data = _session.get(key_url, timeout=30).content
            iv = key.iv.replace("0x", "")[:16].encode()
            cipher = AES.new(key_data, AES.MODE_CBC, iv)
            break

    ts_urls = [base_url + '/' + seg.uri for seg in m3u8_obj.segments]

    os.remove(m3u8_file)
    if not os.listdir(folder_path):
        os.rmdir(folder_path)

    return ts_urls, cipher


def download_segments(ts_urls, cipher, folder_path, session=None):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    _session = session or create_session()

    def _ts_path(url):
        name = url.split('/')[-1][:-3]
        return os.path.join(folder_path, name + '.ts')

    pending = [u for u in ts_urls if not os.path.exists(_ts_path(u))]
    skipped = len(ts_urls) - len(pending)

    if not pending:
        return 0

    pbar = tqdm.tqdm(total=len(ts_urls), initial=skipped, unit='seg',
                     bar_format='  {l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')
    lock = threading.Lock()
    fail_count = 0

    def worker(ts_url):
        nonlocal fail_count
        save_path = _ts_path(ts_url)
        success = False

        for attempt in range(MAX_RETRIES):
            try:
                resp = _session.get(ts_url, timeout=TS_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.content
                    if cipher:
                        data = cipher.decrypt(data)
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    success = True
                    break
            except Exception:
                continue

        with lock:
            pbar.update(1)
            if not success:
                fail_count += 1

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        list(executor.map(worker, pending))

    pbar.close()
    return fail_count


def merge_segments(ts_urls, ts_folder, output_path):
    with open(output_path, 'wb') as out:
        for ts_url in ts_urls:
            name = ts_url.split('/')[-1][:-3]
            ts_path = os.path.join(ts_folder, name + '.ts')
            with open(ts_path, 'rb') as f:
                out.write(f.read())

    for ts_url in ts_urls:
        name = ts_url.split('/')[-1][:-3]
        ts_path = os.path.join(ts_folder, name + '.ts')
        os.remove(ts_path)
    if os.path.isdir(ts_folder) and not os.listdir(ts_folder):
        os.rmdir(ts_folder)
