#!/usr/bin/env python3

import sys
import argparse
from src.config import Config
from src.downloader import download_album

def main():
    parser = argparse.ArgumentParser(description='Video Game Music Downloader')
    parser.add_argument('url', nargs='+', help='Album URL(s) to download')
    parser.add_argument('-o', '--output', default='downloads', help='Output directory')
    parser.add_argument('-f', '--format', choices=['mp3', 'flac', 'both'], default='both', help='Audio format to download')
    parser.add_argument('-b', '--browser', choices=['chrome', 'edge', 'firefox'], default='auto', help='Browser to use')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--no-booklet', action='store_true', help='Skip downloading booklet images')
    parser.add_argument('--retry', action='store_true', help='Retry each resource until download succeeds')
    parser.add_argument('-w', '--workers', type=int, default=4, help='Max concurrent download threads (default: 4)')

    args = parser.parse_args()

    config = Config(
        output_dir=args.output,
        audio_format=args.format,
        browser=args.browser,
        headless=args.headless,
        download_booklet=not args.no_booklet,
        retry=args.retry,
        max_workers=args.workers
    )

    try:
        for url in args.url:
            download_album(config, url)
    except KeyboardInterrupt:
        print('\nDownload interrupted by user')
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()