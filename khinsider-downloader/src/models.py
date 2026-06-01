from dataclasses import dataclass
from typing import List

@dataclass
class TrackInfo:
    cd_number: int
    track_number: int
    title: str
    song_page_url: str
    duration: str = ""

    def get_formatted_filename(self, extension: str) -> str:
        """Generate formatted filename: '01. Song Title.mp3'"""
        return f"{self.track_number:02d}. {self.title}.{extension}"

@dataclass
class BookletImage:
    url: str
    filename: str

@dataclass
class AlbumInfo:
    name: str
    tracks: List[TrackInfo]
    booklet_images: List[BookletImage]