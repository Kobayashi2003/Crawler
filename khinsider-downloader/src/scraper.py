from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from typing import List, Tuple, Dict
from .config import Config
from .models import AlbumInfo, TrackInfo, BookletImage

class KHInsiderScraper:
    def __init__(self, driver, config: Config):
        self.driver = driver
        self.config = config
    
    def get_album_info(self, url: str) -> AlbumInfo:
        self.driver.get(url)
        time.sleep(self.config.page_delay)
        
        album_name = self._extract_album_name()
        tracks = self._extract_tracks()
        booklet_images = self._extract_booklet_images()
        
        return AlbumInfo(
            name=album_name,
            tracks=tracks,
            booklet_images=booklet_images
        )
    
    def get_download_urls(self, song_page_url: str) -> Tuple[str, List[str]]:
        self.driver.get(song_page_url)
        time.sleep(self.config.page_delay)
        
        song_name = self._extract_song_name()
        download_urls = self._extract_download_urls()
        
        return song_name, download_urls
    
    def _extract_album_name(self) -> str:
        try:
            title_element = self.driver.find_element(By.TAG_NAME, 'h2')
            return title_element.text.strip()
        except:
            return "Unknown Album"
    
    def _extract_tracks(self) -> List[TrackInfo]:
        tracks = []
        try:
            table = self.driver.find_element(By.ID, 'songlist')
            rows = table.find_elements(By.TAG_NAME, 'tr')
            
            # Check if table has CD column by examining header
            has_cd_column = self._has_cd_column(table)
            
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, 'td')
                if len(cells) >= 4:  # Minimum cells needed
                    try:
                        if has_cd_column:
                            # Format with CD column: [play] [CD] [#] [Title] [Duration] [MP3] [FLAC] [Download] [Playlist]
                            cd_number = int(cells[1].text.strip())
                            track_text = cells[2].text.strip()
                            title_cell = cells[3]
                            duration_cell = cells[4]
                        else:
                            # Format without CD column: [play] [#] [Title] [Duration] [MP3] [FLAC] [Download] [Playlist]
                            cd_number = 1  # Default to CD1 when no CD column
                            track_text = cells[1].text.strip()
                            title_cell = cells[2]
                            duration_cell = cells[3]
                        
                        # Extract track number
                        if track_text.endswith('.'):
                            track_number = int(track_text[:-1])
                        else:
                            track_number = int(track_text)
                        
                        # Extract song title and URL
                        link = title_cell.find_element(By.TAG_NAME, 'a')
                        title = link.text.strip()
                        song_url = link.get_attribute('href')
                        
                        # Extract duration
                        duration_link = duration_cell.find_element(By.TAG_NAME, 'a')
                        duration = duration_link.text.strip()
                        
                        if song_url and not song_url.endswith('#'):
                            tracks.append(TrackInfo(
                                cd_number=cd_number,
                                track_number=track_number,
                                title=title,
                                song_page_url=song_url,
                                duration=duration
                            ))
                    except (ValueError, IndexError) as e:
                        print(f"Error parsing track row: {e}")
                        continue
        except Exception as e:
            print(f"Error extracting tracks: {e}")
        
        return tracks
    
    def _has_cd_column(self, table) -> bool:
        """Check if the table has a CD column by examining the header"""
        try:
            header_row = table.find_element(By.ID, 'songlist_header')
            header_cells = header_row.find_elements(By.TAG_NAME, 'th')
            
            # Look for "CD" text in header cells
            for cell in header_cells:
                if 'CD' in cell.text.upper():
                    return True
            return False
        except:
            # If we can't find header, assume no CD column for safety
            return False
    
    def _extract_song_name(self) -> str:
        try:
            paragraphs = self.driver.find_elements(By.TAG_NAME, 'p')
            for p in paragraphs:
                text = p.text
                if 'Song name:' in text:
                    return text.split('Song name:')[1].strip()
        except:
            pass
        return "Unknown Song"
    
    def _extract_download_urls(self) -> List[str]:
        download_urls = []
        try:
            # Method 1: Look for links with songDownloadLink class
            download_links = self.driver.find_elements(By.CLASS_NAME, 'songDownloadLink')
            for link_span in download_links:
                try:
                    # The span contains the link, get the parent <a> tag
                    parent_link = link_span.find_element(By.XPATH, '..')
                    href = parent_link.get_attribute('href')
                    if href and self._is_valid_audio_url(href):
                        download_urls.append(href)
                except:
                    continue
            
            # Method 2: Look for download links with specific patterns if Method 1 fails
            if not download_urls:
                download_domains = [
                    'vgmsite.com',
                    'eta.vgmtreasurechest.com',
                    'vgmtreasurechest.com'
                ]
                
                links = self.driver.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    href = link.get_attribute('href')
                    if href:
                        # Check if it's a download link from known domains
                        is_download_link = any(domain in href for domain in download_domains)
                        
                        # Also check for links with audio file extensions
                        has_audio_extension = any(ext in href.lower() for ext in ['.mp3', '.flac', '.ogg', '.wav'])
                        
                        if is_download_link and has_audio_extension:
                            if self._is_valid_audio_url(href):
                                download_urls.append(href)
            
            # Method 3: Fallback - look for any links with audio extensions
            if not download_urls:
                print("No download URLs found with known methods, searching for any audio links...")
                links = self.driver.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    href = link.get_attribute('href')
                    if href and href.startswith('http') and any(ext in href.lower() for ext in ['.mp3', '.flac']):
                        if self._is_valid_audio_url(href):
                            download_urls.append(href)
                                
        except Exception as e:
            print(f"Error extracting download URLs: {e}")
        
        return download_urls
    
    def _is_valid_audio_url(self, url: str) -> bool:
        """Check if URL matches the configured audio format"""
        url_lower = url.lower()
        
        if self.config.audio_format == 'both':
            return '.mp3' in url_lower or '.flac' in url_lower
        elif self.config.audio_format == 'mp3':
            return '.mp3' in url_lower
        elif self.config.audio_format == 'flac':
            return '.flac' in url_lower
        
        return False
    
    def _extract_booklet_images(self) -> List[BookletImage]:
        booklet_images = []
        try:
            # Look for album images in the table or div containers
            album_image_divs = self.driver.find_elements(By.CLASS_NAME, 'albumImage')
            
            for div in album_image_divs:
                try:
                    # Find the link to the full-size image
                    link = div.find_element(By.TAG_NAME, 'a')
                    full_image_url = link.get_attribute('href')
                    
                    # Find the thumbnail image for the filename
                    img = div.find_element(By.TAG_NAME, 'img')
                    thumb_url = img.get_attribute('src')
                    
                    if full_image_url and thumb_url:
                        # Extract filename from full image URL
                        filename = full_image_url.split('/')[-1]
                        
                        booklet_images.append(BookletImage(
                            url=full_image_url,
                            filename=filename
                        ))
                except Exception as e:
                    print(f"Error processing booklet image: {e}")
                    continue
            
            # Alternative: Look for images in table cells if no albumImage divs found
            if not booklet_images:
                tables = self.driver.find_elements(By.TAG_NAME, 'table')
                for table in tables:
                    links = table.find_elements(By.TAG_NAME, 'a')
                    for link in links:
                        href = link.get_attribute('href')
                        if href and any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                            filename = href.split('/')[-1]
                            booklet_images.append(BookletImage(
                                url=href,
                                filename=filename
                            ))
        
        except Exception as e:
            print(f"Error extracting booklet images: {e}")
        
        return booklet_images