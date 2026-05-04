#!/usr/bin/env python3

import os
import sys


def _prompt(label, last='', show_last=True):
    """Prompt with default from last run. Enter reuses the last value."""
    if last and show_last:
        val = input(f'{label} [{last}]: ').strip()
    else:
        val = input(f'{label}: ').strip()
    return val if val else last


def main():
    from src.utils.config import get_last_input

    last_mode = get_last_input('mode', '')
    print('Jable Downloader')
    print('=' * 40)
    print('  1. Download video(s) by URL')
    print('  2. Download all videos from an artist page')
    print('=' * 40)

    choice = _prompt('Select mode [1/2]', last_mode)

    if choice == '1':
        download_videos()
    elif choice == '2':
        download_artist()
    else:
        print('Invalid choice.')
        sys.exit(1)


def download_videos():
    from src.video_downloader import download_video
    from src.utils.helpers import is_video_url
    from src.utils.config import load_config, get_last_input, save_last_input
    from src.utils.proxy import load_proxy_pool

    urls_input = _prompt('Enter video URL(s) (space-separated)',
                         get_last_input('video_urls', '')).split()
    if not urls_input:
        print('No URLs provided.')
        sys.exit(1)

    folder_path = _prompt('Output folder (Enter = current dir)',
                          get_last_input('video_folder', ''))
    if not folder_path:
        folder_path = os.getcwd()
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    save_last_input(mode='1', video_urls=' '.join(urls_input), video_folder=folder_path)

    proxy_pool = load_proxy_pool(load_config())

    for url in urls_input:
        if not is_video_url(url):
            print(f'Invalid jable video URL: {url}')
            continue
        print(f'\nDownloading: {url}')
        download_video(url, folder_path, proxy_pool=proxy_pool)

    if proxy_pool:
        proxy_pool.cleanup()


def download_artist():
    from src.artist_downloader import main as artist_main
    from src.utils.config import get_last_input, save_last_input

    url = _prompt('Enter artist page URL', get_last_input('artist_url', ''))
    if not url:
        print('No URL provided.')
        sys.exit(1)

    folder_path = _prompt('Output folder (Enter = current dir)',
                          get_last_input('artist_folder', ''))
    sort_order = _prompt('Sort order (best/latest/views/favorites)',
                         get_last_input('artist_sort', ''))
    template = _prompt('Naming template ({video_id}, {title}, {artist})',
                       get_last_input('artist_template', ''))
    limit = _prompt('Max videos to download (Enter = all)',
                    get_last_input('artist_limit', ''))
    last_confirm = get_last_input('artist_no_confirm', '')
    no_confirm = _prompt('Skip confirmation? [y/N]', last_confirm).lower() == 'y'

    save_last_input(
        mode='2', artist_url=url, artist_folder=folder_path,
        artist_sort=sort_order, artist_template=template,
        artist_limit=limit, artist_no_confirm='y' if no_confirm else 'n',
    )

    argv = [url]
    if folder_path:
        argv.extend(['-p', folder_path])
    if sort_order:
        argv.extend(['--sort', sort_order])
    if template:
        argv.extend(['--template', template])
    if limit:
        argv.extend(['--limit', limit])
    if no_confirm:
        argv.append('--no-confirm')

    sys.argv = ['download_artist'] + argv
    artist_main()


if __name__ == '__main__':
    main()
