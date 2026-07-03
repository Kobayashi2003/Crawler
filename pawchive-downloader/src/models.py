from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


# Marker stored in cache for posts that were fetched but genuinely have no text
# content, so we can tell "not fetched yet" ("") apart from "fetched, empty".
NO_CONTENT_MARKER = "<NO_CONTENT>"


# ==================== Core Data Models ====================

@dataclass
class Artist:
    """A tracked creator. `id` is `{service}_{user_id}` and matches kemono's ids."""
    id: str
    service: str
    user_id: str
    name: str
    url: str = ""
    alias: str = ""
    last_date: Optional[str] = None
    timer: Optional[Dict] = None
    ignore: bool = False
    completed: bool = False
    config: Dict = field(default_factory=dict)
    filter: Dict = field(default_factory=dict)

    def display_name(self) -> str:
        return self.alias or self.name


@dataclass
class Post:
    """A single post and its download state."""
    id: str
    user: str
    service: str
    title: str = ""
    content: str = ""
    published: str = ""
    added: str = ""
    edited: Optional[str] = None
    file: Optional[Dict] = None
    attachments: List[Dict] = field(default_factory=list)
    done: bool = False
    failed_files: List[str] = field(default_factory=list)


@dataclass
class Profile:
    """Creator profile returned by the API. Pawchive does not expose a post
    count, so `updated` is what we diff against to detect changes cheaply."""
    id: str
    name: str = ""
    service: str = ""
    public_id: Optional[str] = None
    indexed: str = ""
    updated: str = ""
    cached_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ==================== Configuration ====================

@dataclass
class Config:
    """Application configuration (global; artists may override a subset)."""
    # Directories
    data_dir: str = "data"
    cache_dir: str = "cache"
    logs_dir: str = "logs"
    temp_dir: str = "temp"
    download_dir: str = "downloads"

    # Scheduling & filtering
    global_timer: Optional[Dict] = None
    global_filter: Dict = field(default_factory=dict)

    # Network
    retry_delay: int = 5
    request_timeout: int = 30
    proxy: str = ""  # e.g. "http://127.0.0.1:7890"; applied to all requests
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) "
        "Gecko/20100101 Firefox/135.0"
    )

    # Concurrency (total ≈ artists × posts × files)
    max_concurrent_artists: int = 3
    max_concurrent_posts: int = 5
    max_concurrent_files: int = 10

    # Path templates
    date_format: str = "%Y.%m.%d"
    artist_folder_template: str = "{service}/{name}"
    post_folder_template: str = "[{published}] {title}"
    file_template: str = "{idx}"

    # Download behaviour
    save_content: bool = True
    save_empty_posts: bool = False
    rename_images_only: bool = True
    image_extensions: set = field(
        default_factory=lambda: {'.jpe', '.jpg', '.jpeg', '.png', '.gif', '.webp'}
    )


# ==================== History ====================

@dataclass
class HistoryRecord:
    command: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True
    artist_id: Optional[str] = None
    params: Dict = field(default_factory=dict)
    note: str = ""


# ==================== Download Results ====================

@dataclass
class DownloadResult:
    """Outcome of downloading one artist."""
    artist_id: str
    success: bool = True
    posts_downloaded: int = 0
    posts_failed: int = 0
    skipped: bool = False


# ==================== Scheduler Models ====================

class TaskType:
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class TaskStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DownloadTask:
    artist_id: str
    from_date: Optional[str] = None
    until_date: Optional[str] = None
    task_type: str = TaskType.MANUAL
    status: str = TaskStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

    def __eq__(self, other):
        return isinstance(other, DownloadTask) and (
            (self.artist_id, self.from_date, self.until_date)
            == (other.artist_id, other.from_date, other.until_date)
        )

    def __hash__(self):
        return hash((self.artist_id, self.from_date, self.until_date))
