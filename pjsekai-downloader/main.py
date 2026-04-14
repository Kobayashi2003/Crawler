#!/usr/bin/env python3

from src.downloader import PjsekaiDownloader

if __name__ == '__main__':
    downloader = PjsekaiDownloader(output_dir='downloads')
    downloader.download_all()
