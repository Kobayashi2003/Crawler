import threading

from .naming import human_size


class Notifier:
    """Console download progress; the only hook the downloader ever calls.

    `enabled=False` makes it a no-op. Files download concurrently, so progress
    is tracked per file and the size is printed on the first callback (there is
    no separate "started" event).
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._last: dict = {}
        self._lock = threading.Lock()

    def on_download_progress(self, filename: str, downloaded: int, total_size: int):
        if not self.enabled or total_size <= 0:
            return
        percent = int(downloaded / total_size * 100)
        with self._lock:
            if filename not in self._last:
                self._last[filename] = -1
                print(f"    v {filename} ({human_size(total_size)})")
            if percent < self._last[filename] + 25:
                return
            self._last[filename] = percent
            if downloaded >= total_size:
                del self._last[filename]
        print(f"      {filename} - {percent}%")
