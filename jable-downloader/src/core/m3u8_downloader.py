import os
import re
import copy
import tqdm

from functools import partial
from concurrent import futures

import m3u8
import requests
import urllib.request
from Crypto.Cipher import AES

from ..utils.config import USER_AGENT
from .browser import create_driver


def downloadM3U8(url, folderPath):
    driver = create_driver()
    driver.get(url=url)

    m3u8urls = re.findall("https://.+m3u8", driver.page_source)
    m3u8url = m3u8urls[0]
    driver.quit()

    if not os.path.exists(folderPath):
        os.makedirs(folderPath)
    m3u8file = os.path.join(folderPath, f'{url.split("/")[-2]}.m3u8')
    urllib.request.urlretrieve(m3u8url, m3u8file)

    m3u8obj = m3u8.load(m3u8file)
    downloadUrl = '/'.join(m3u8url.split('/')[:-1])

    m3u8uri = ''
    m3u8iv = ''
    for key in m3u8obj.keys:
        if key:
            m3u8uri = key.uri
            m3u8iv = key.iv

    if m3u8uri:
        m3u8keyUrl = downloadUrl + '/' + m3u8uri
        m3u8key = requests.get(m3u8keyUrl, headers={
            'User-Agent': USER_AGENT,
        }, timeout=10).content
        iv = m3u8iv.replace("0x", "")[:16].encode()
        ci = AES.new(m3u8key, AES.MODE_CBC, iv)
    else:
        ci = ''

    tsUrls = []
    for seg in m3u8obj.segments:
        tsUrls.append(downloadUrl + '/' + seg.uri)

    os.remove(m3u8file)
    if not os.listdir(folderPath):
        os.rmdir(folderPath)

    return tsUrls, ci


def downloadTS(pbar, downloadList, ci, folderPath, tsUrl):
    fileName = tsUrl.split('/')[-1][0:-3]
    saveName = os.path.join(folderPath, fileName + ".ts")
    if os.path.exists(saveName):
        downloadList.remove(tsUrl)
        pbar.update(1)
    else:
        response = requests.get(tsUrl, headers={
            'User-Agent': USER_AGENT,
        }, timeout=10)
        if response.status_code == 200:
            content_ts = response.content
            if ci:
                content_ts = ci.decrypt(content_ts)
            with open(saveName, 'wb') as f:
                f.write(content_ts)
            downloadList.remove(tsUrl)
            pbar.update(1)
        else:
            ...


def downloadTSList(tsUrls, ci, folderPath):
    if not os.path.exists(folderPath):
        os.makedirs(folderPath)

    downloadList = copy.deepcopy(tsUrls)
    pbar = tqdm.tqdm(total=len(downloadList))

    while downloadList:
        with futures.ThreadPoolExecutor(max_workers=32) as executor:
            executor.map(partial(downloadTS, pbar, downloadList, ci, folderPath), downloadList)


def mergeTSFiles(tsUrls, tsFolderPath, savePath):
    with open(savePath, 'wb') as f:
        for ts in tqdm.tqdm(tsUrls):
            tsName = ts.split('/')[-1][0:-3]
            tsPath = os.path.join(tsFolderPath, tsName + ".ts")
            with open(tsPath, 'rb') as f1:
                f.write(f1.read())

    for ts in tsUrls:
        tsName = ts.split('/')[-1][0:-3]
        tsPath = os.path.join(tsFolderPath, tsName + ".ts")
        os.remove(tsPath)
    if not os.listdir(tsFolderPath):
        os.rmdir(tsFolderPath)
