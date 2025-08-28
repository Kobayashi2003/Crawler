import time
from .config import Config
from .browser_manager import BrowserManager
from .scraper import KHInsiderScraper
from .file_downloader import FileDownloader
from .models import AlbumInfo

class VideoGameMusicDownloader:
    def __init__(self, config: Config):
        self.config = config
        self.browser_manager = BrowserManager(config)
        self.file_downloader = FileDownloader(config)
        self.driver = None
        self.scraper = None
    
    def download_album(self, album_url: str):
        try:
            self._initialize()
            self._download_album_content(album_url)
        finally:
            self._cleanup()
    
    def _initialize(self):
        print("Initializing browser...")
        self.driver = self.browser_manager.setup_driver()
        self.scraper = KHInsiderScraper(self.driver, self.config)
    
    def _download_album_content(self, album_url: str):
        print("Extracting album information...")
        album_info = self.scraper.get_album_info(album_url)
        
        print(f"Album: {album_info.name}")
        print(f"Found {len(album_info.tracks)} tracks")
        print(f"Found {len(album_info.booklet_images)} booklet images")
        
        # Download booklet images
        if self.config.download_booklet and album_info.booklet_images:
            self._download_booklet_images(album_info)
        
        # Download tracks
        if album_info.tracks:
            self._download_tracks(album_info)
        else:
            print("No tracks found!")
    
    def _download_booklet_images(self, album_info: AlbumInfo):
        print("\n=== Downloading Booklet Images ===")
        booklet_success = 0
        
        for i, booklet_image in enumerate(album_info.booklet_images, 1):
            print(f"Downloading booklet image {i}/{len(album_info.booklet_images)}: {booklet_image.filename}")
            
            if self.file_downloader.download_booklet_image(
                booklet_image.url, 
                album_info.name, 
                booklet_image.filename
            ):
                booklet_success += 1
            
            time.sleep(self.config.download_delay)
        
        print(f"Downloaded {booklet_success}/{len(album_info.booklet_images)} booklet images")
    
    def _download_tracks(self, album_info: AlbumInfo):
        print("\n=== Downloading Music Tracks ===")
        
        # Group tracks by CD
        cd_tracks = album_info.get_tracks_by_cd()
        total_cds = len(cd_tracks)
        
        total_tracks = len(album_info.tracks)
        successful_downloads = 0
        total_files = 0
        current_track = 0
        
        if total_cds > 1:
            print(f"Album has {total_cds} CDs")
        else:
            print("Single CD album")
        
        for cd_number in sorted(cd_tracks.keys()):
            tracks = cd_tracks[cd_number]
            
            if total_cds > 1:
                print(f"\n--- Processing CD {cd_number} ({len(tracks)} tracks) ---")
            else:
                print(f"\n--- Processing {len(tracks)} tracks ---")
            
            for track in tracks:
                current_track += 1
                
                if total_cds > 1:
                    print(f"\nProcessing track {current_track}/{total_tracks}: CD{track.cd_number}-{track.track_number:02d}. {track.title}")
                else:
                    print(f"\nProcessing track {current_track}/{total_tracks}: {track.track_number:02d}. {track.title}")
                
                try:
                    # Get download URLs for this track
                    song_name, download_urls = self.scraper.get_download_urls(track.song_page_url)
                    
                    if not download_urls:
                        print("No download URLs found for this track")
                        continue
                    
                    # Download each format (MP3/FLAC)
                    for url in download_urls:
                        total_files += 1
                        if self.file_downloader.download_track(url, album_info.name, track, total_cds):
                            successful_downloads += 1
                        
                        time.sleep(self.config.download_delay)
                    
                    time.sleep(self.config.page_delay)
                    
                except Exception as e:
                    print(f"Error processing track {current_track}: {e}")
                    continue
        
        print(f"\n=== Download Summary ===")
        print(f"Successfully downloaded: {successful_downloads}/{total_files} files")
        print(f"Processed: {current_track}/{total_tracks} tracks")
    
    def _cleanup(self):
        if self.browser_manager:
            self.browser_manager.quit()