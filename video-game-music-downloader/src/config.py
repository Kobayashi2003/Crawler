from dataclasses import dataclass
from typing import Literal

@dataclass
class Config:
    output_dir: str = "downloads"
    audio_format: Literal["mp3", "flac", "both"] = "both"
    browser: Literal["chrome", "edge", "firefox", "auto"] = "auto"
    headless: bool = False
    download_delay: float = 1.0
    page_delay: float = 2.0
    download_booklet: bool = True
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"