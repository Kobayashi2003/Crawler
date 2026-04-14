#!/usr/bin/env python3

import os
import sys


def main():
    print('Jable Downloader')
    print('=' * 40)
    print('  1. Download video(s) by URL')
    print('  2. Download all videos from a model page')
    print('=' * 40)

    choice = input('Select mode [1/2]: ').strip()

    if choice == '1':
        download_videos()
    elif choice == '2':
        download_model()
    else:
        print('Invalid choice.')
        sys.exit(1)


def download_videos():
    from src.downloader import isJableVideoUrl, downloadVideo

    urls_input = input('Enter video URL(s) (space-separated): ').strip().split()
    if not urls_input:
        print('No URLs provided.')
        sys.exit(1)

    folder_path = input('Output folder (press Enter for current directory): ').strip()
    if not folder_path:
        folder_path = os.getcwd()
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    for url in urls_input:
        if not isJableVideoUrl(url):
            print(f'Invalid jable video URL: {url}')
            continue
        print(f'\nDownloading: {url}')
        downloadVideo(url, folder_path)


def download_model():
    from src.model_downloader import main as model_main
    # Replace sys.argv so argparse in model_main picks up the right args
    import argparse

    url = input('Enter model page URL: ').strip()
    if not url:
        print('No URL provided.')
        sys.exit(1)

    folder_path = input('Output folder (press Enter for current directory): ').strip()
    sort_order = input('Sort order (best/latest/views/favorites, press Enter to skip): ').strip()
    limit = input('Max videos to download (press Enter for all): ').strip()
    no_confirm = input('Skip confirmation? [y/N]: ').strip().lower() == 'y'

    argv = [url]
    if folder_path:
        argv.extend(['-p', folder_path])
    if sort_order:
        argv.extend(['--sort', sort_order])
    if limit:
        argv.extend(['--limit', limit])
    if no_confirm:
        argv.append('--no-confirm')

    sys.argv = ['download_model'] + argv
    model_main()


if __name__ == '__main__':
    main()
