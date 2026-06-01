import time
from typing import List
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from .config import Config
from .models import AlbumInfo, TrackInfo, BookletImage


def scrape_album(driver, url: str, config: Config) -> AlbumInfo:
    driver.get(url)
    time.sleep(config.page_delay)
    return AlbumInfo(
        name=_get_album_name(driver),
        tracks=_get_tracks(driver),
        booklet_images=_get_booklet_images(driver),
    )


def scrape_download_urls(driver, url: str, config: Config) -> List[str]:
    driver.get(url)
    time.sleep(config.page_delay)
    return _get_download_urls(driver, config.audio_format)


# --- private helpers ---

def _get_album_name(driver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, 'h2').text.strip()
    except Exception:
        return 'Unknown Album'


def _get_tracks(driver) -> List[TrackInfo]:
    tracks = []
    try:
        table = driver.find_element(By.ID, 'songlist')
        has_cd_col = _has_cd_column(table)
        min_cells = 5 if has_cd_col else 4

        for row in table.find_elements(By.TAG_NAME, 'tr'):
            cells = row.find_elements(By.TAG_NAME, 'td')
            if len(cells) < min_cells:
                continue
            try:
                if has_cd_col:
                    cd_number = int(cells[1].text.strip())
                    track_text = cells[2].text.strip()
                    title_cell, duration_cell = cells[3], cells[4]
                else:
                    cd_number = 1
                    track_text = cells[1].text.strip()
                    title_cell, duration_cell = cells[2], cells[3]

                track_number = int(track_text.rstrip('.'))
                link = title_cell.find_element(By.TAG_NAME, 'a')
                song_url = link.get_attribute('href')
                if not song_url or song_url.endswith('#'):
                    continue

                try:
                    duration = duration_cell.find_element(By.TAG_NAME, 'a').text.strip()
                except Exception:
                    duration = duration_cell.text.strip()

                tracks.append(TrackInfo(
                    cd_number=cd_number,
                    track_number=track_number,
                    title=link.text.strip(),
                    song_page_url=song_url,
                    duration=duration,
                ))
            except Exception as e:
                print(f'Error parsing track row: {e}')
    except Exception as e:
        print(f'Error extracting tracks: {e}')
    return tracks


def _has_cd_column(table) -> bool:
    try:
        header = table.find_element(By.ID, 'songlist_header')
        return any('CD' in cell.text.upper() for cell in header.find_elements(By.TAG_NAME, 'th'))
    except Exception:
        return False


def _get_download_urls(driver, audio_format: str) -> List[str]:
    urls = []
    seen = set()

    def add(href: str):
        if href and href not in seen and _is_audio_url(href, audio_format):
            seen.add(href)
            urls.append(href)

    try:
        # Method 1: links with songDownloadLink class
        for span in driver.find_elements(By.CLASS_NAME, 'songDownloadLink'):
            try:
                add(span.find_element(By.XPATH, '..').get_attribute('href'))
            except Exception:
                continue

        # Method 2: known download domains
        if not urls:
            known_domains = ['vgmsite.com', 'eta.vgmtreasurechest.com', 'vgmtreasurechest.com']
            for link in driver.find_elements(By.TAG_NAME, 'a'):
                href = link.get_attribute('href') or ''
                if any(d in href for d in known_domains):
                    add(href)

        # Method 3: fallback — any audio link on the page
        if not urls:
            print('Falling back to searching all audio links...')
            for link in driver.find_elements(By.TAG_NAME, 'a'):
                href = link.get_attribute('href') or ''
                if href.startswith('http'):
                    add(href)
    except Exception as e:
        print(f'Error extracting download URLs: {e}')
    return urls


def _get_booklet_images(driver) -> List[BookletImage]:
    images = []
    try:
        for div in driver.find_elements(By.CLASS_NAME, 'albumImage'):
            try:
                full_url = div.find_element(By.TAG_NAME, 'a').get_attribute('href')
                if full_url:
                    filename = urlparse(full_url).path.split('/')[-1]
                    images.append(BookletImage(url=full_url, filename=filename))
            except Exception as e:
                print(f'Error processing booklet image: {e}')

        if not images:
            for table in driver.find_elements(By.TAG_NAME, 'table'):
                for link in table.find_elements(By.TAG_NAME, 'a'):
                    href = link.get_attribute('href') or ''
                    path = urlparse(href).path
                    if any(path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                        filename = path.split('/')[-1]
                        images.append(BookletImage(url=href, filename=filename))
    except Exception as e:
        print(f'Error extracting booklet images: {e}')
    return images


def _is_audio_url(url: str, audio_format: str) -> bool:
    url_lower = url.lower()
    if audio_format == 'both':
        return '.mp3' in url_lower or '.flac' in url_lower
    return f'.{audio_format}' in url_lower