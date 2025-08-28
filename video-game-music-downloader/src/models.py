from dataclasses import dataclass
from typing import List, Dict, Optional

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
    
    def get_tracks_by_cd(self) -> Dict[int, List[TrackInfo]]:
        """Group tracks by CD number"""
        cd_tracks = {}
        for track in self.tracks:
            if track.cd_number not in cd_tracks:
                cd_tracks[track.cd_number] = []
            cd_tracks[track.cd_number].append(track)
        return cd_tracks