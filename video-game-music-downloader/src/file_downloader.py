import os
import re
import requests
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional
from .config import Config
from .models import TrackInfo

class FileDownloader:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.user_agent
        })
    
    def download_track(self, url: str, album_name: str, track_info: TrackInfo, total_cds: int = 1) -> bool:
        try:
            # Determine file format from URL
            file_format = self._get_file_format(url)
            if not file_format:
                print(f"Unknown file format for URL: {url}")
                return False
            
            filename = track_info.get_formatted_filename(file_format)
            filepath = self._get_track_filepath(album_name, track_info.cd_number, file_format, filename, total_cds)
            
            if filepath.exists():
                print(f"Track already exists: {filename}")
                return True
            
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = filepath.stat().st_size / (1024 * 1024)
            print(f"Downloaded track: {filename} ({file_size:.2f} MB)")
            return True
            
        except Exception as e:
            print(f"Error downloading track {url}: {e}")
            return False
    
    def download_booklet_image(self, url: str, album_name: str, filename: str) -> bool:
        try:
            safe_filename = self._sanitize_filename(filename)
            filepath = self._get_booklet_filepath(album_name, safe_filename)
            
            if filepath.exists():
                print(f"Booklet image already exists: {safe_filename}")
                return True
            
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = filepath.stat().st_size / (1024 * 1024)
            print(f"Downloaded booklet: {safe_filename} ({file_size:.2f} MB)")
            return True
            
        except Exception as e:
            print(f"Error downloading booklet image {url}: {e}")
            return False
    
    def _get_file_format(self, url: str) -> Optional[str]:
        """Extract file format from URL"""
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if '.mp3' in filename.lower():
            return 'mp3'
        elif '.flac' in filename.lower():
            return 'flac'
        
        return None
    
    def _sanitize_filename(self, filename: str) -> str:
        # Remove URL encoding
        filename = requests.utils.unquote(filename)
        # Replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove non-printable characters but keep unicode
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        # Normalize whitespace
        filename = re.sub(r'\s+', ' ', filename).strip()
        # Limit length
        return filename[:200]
    
    def _get_track_filepath(self, album_name: str, cd_number: int, file_format: str, filename: str, total_cds: int = 1) -> Path:
        """
        Generate path: 
        - Multiple CDs: downloads/Album Name/Music/MP3/CD1/01. Song Title.mp3
        - Single CD: downloads/Album Name/Music/MP3/01. Song Title.mp3
        """
        safe_album_name = self._sanitize_filename(album_name)
        format_folder = file_format.upper()
        
        if total_cds > 1:
            # Multiple CDs: create CD subfolder
            cd_folder = f"CD{cd_number}"
            return Path(self.config.output_dir) / safe_album_name / "Music" / format_folder / cd_folder / filename
        else:
            # Single CD: no CD subfolder needed
            return Path(self.config.output_dir) / safe_album_name / "Music" / format_folder / filename
    
    def _get_booklet_filepath(self, album_name: str, filename: str) -> Path:
        """
        Generate path: downloads/Album Name/Booklet/image.jpg
        """
        safe_album_name = self._sanitize_filename(album_name)
        return Path(self.config.output_dir) / safe_album_name / "Booklet" / filename