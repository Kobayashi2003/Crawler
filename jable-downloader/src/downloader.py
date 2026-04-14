import os
import time

import requests
from bs4 import BeautifulSoup

from .config import USER_AGENT
from .browser import create_driver
from .m3u8_downloader import downloadM3U8, downloadTSList, mergeTSFiles
from .encoder import ffmpegEncode
from .utils import isJableVideoUrl


def downloadCover(url, folderPath):
    driver = create_driver()
    driver.get(url=url)

    if not os.path.exists(folderPath):
        os.mkdir(folderPath)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    cover_url = soup.find('meta', property='og:image')['content']
    cover_name = cover_url.split('/')[-1]
    cover_path = os.path.join(folderPath, cover_name)
    for attempt in range(3):
        try:
            resp = requests.get(cover_url, headers={
                'User-Agent': USER_AGENT,
            }, timeout=30)
            resp.raise_for_status()
            with open(cover_path, 'wb') as f:
                f.write(resp.content)
            break
        except Exception as e:
            if attempt < 2:
                print(f'  Cover download retry ({attempt + 1}/3): {e}')
                time.sleep(2)
            else:
                print(f'  Warning: Failed to download cover: {e}')


def downloadVideo(url, folderPath, folder_name=None):
    videoId = url.rstrip('/').split('/')[-1]
    folderName = folder_name or videoId
    videoFolder = os.path.join(folderPath, folderName)

    coverFolder = videoFolder
    m3u8Folder  = os.path.join(videoFolder, 'm3u8')
    tsFolder    = os.path.join(videoFolder, 'ts')
    videoFile   = os.path.join(videoFolder, videoId + '.mp4')
    encodeFile  = os.path.join(videoFolder, 'f_' + videoId + '.mp4')

    # Skip if already downloaded
    if os.path.exists(videoFile):
        print(f'Already downloaded: {folderName}, skipping.')
        return

    downloadCover(url, coverFolder)
    tsUrls, ci = downloadM3U8(url, m3u8Folder)
    downloadTSList(tsUrls, ci, tsFolder)
    mergeTSFiles(tsUrls, tsFolder, videoFile)
    if ffmpegEncode(videoFile, encodeFile):
        print('Encode success')
        os.remove(videoFile)
        os.rename(encodeFile, videoFile)
    else:
        print('Encode failed')
