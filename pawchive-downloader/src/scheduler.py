import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from queue import Queue
from typing import Dict, List, Optional

from .downloader import Downloader
from .logger import Logger
from .models import DownloadTask, TaskStatus, TaskType
from .storage import Storage


class Scheduler:
    """Runs downloads on a bounded thread pool.

    Tasks arrive either manually (``queue_manual``/``queue_batch``) or from
    per-artist / global timers checked once a second in a background loop.
    One artist is never queued twice concurrently.
    """

    def __init__(self, storage: Storage, downloader: Downloader, logger: Logger,
                 global_timer: Optional[Dict], max_workers: int = 3):
        self.storage = storage
        self.downloader = downloader
        self.logger = logger
        self.global_timer = global_timer
        self.max_workers = max_workers

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self._next_runs: Dict[str, datetime] = {}

        self.queue: "Queue[DownloadTask]" = Queue()
        self.queued: set = set()
        self.active: Dict[str, DownloadTask] = {}
        self.completed: List[DownloadTask] = []
        self.lock = threading.Lock()

    # ==================== Lifecycle ====================

    def start(self):
        if self.running:
            return
        self.running = True
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.logger.scheduler_started(max_workers=self.max_workers)

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        self.logger.scheduler_stopped()

    def cancel_all(self) -> int:
        with self.lock:
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except Exception:
                    break
            self.queued.clear()
            active = len(self.active)
        self.downloader.stop()
        deadline = time.time() + 10
        while time.time() < deadline:
            with self.lock:
                if not self.active:
                    break
            time.sleep(0.1)
        self.downloader.resume()
        return active

    # ==================== Queueing ====================

    def queue_manual(self, artist_id: str, from_date: str = None, until_date: str = None) -> bool:
        return self._add(DownloadTask(artist_id, from_date, until_date, TaskType.MANUAL))

    def queue_batch(self, artist_ids: List[str]) -> int:
        return sum(self._add(DownloadTask(aid, task_type=TaskType.MANUAL)) for aid in artist_ids)

    def _add(self, task: DownloadTask) -> bool:
        with self.lock:
            if task.artist_id in self.active:
                return False
            if any(t.artist_id == task.artist_id for t in self.queued):
                return False
            self.queued.add(task)
            self.queue.put(task)
            self.logger.scheduler_queued(artist_id=task.artist_id, type=task.task_type)
            return True

    # ==================== Status ====================

    def status(self) -> Dict[str, int]:
        with self.lock:
            return {'queued': self.queue.qsize(), 'running': len(self.active),
                    'completed': len(self.completed)}

    def list_active(self) -> List[DownloadTask]:
        with self.lock:
            return list(self.active.values())

    def list_queued(self) -> List[DownloadTask]:
        with self.lock:
            return list(self.queue.queue)

    # ==================== Loop ====================

    def _loop(self):
        while self.running:
            try:
                self._check_timers()
                self._process()
                time.sleep(1)
            except Exception as e:
                self.logger.scheduler_error(error=str(e), level='error')
                time.sleep(5)

    def _process(self):
        with self.lock:
            if len(self.active) >= self.max_workers or self.queue.empty():
                return
            task = self.queue.get_nowait()
            self.queued.discard(task)
            self.active[task.artist_id] = task
        future = self._executor.submit(self._execute, task)
        future.add_done_callback(lambda f: self._finish(task))

    def _execute(self, task: DownloadTask):
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        try:
            artist = self.storage.get_artist(task.artist_id)
            if not artist:
                raise Exception(f"Artist {task.artist_id} not found")
            self.downloader.download_artist(artist, task.from_date, task.until_date)
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            self.logger.scheduler_task_failed(artist_id=task.artist_id, error=str(e), level='error')
        finally:
            task.finished_at = datetime.now()

    def _finish(self, task: DownloadTask):
        with self.lock:
            self.active.pop(task.artist_id, None)
            self.completed.append(task)
            self.completed = self.completed[-100:]

    # ==================== Timers ====================

    def _check_timers(self):
        for artist in self.storage.get_artists():
            if artist.ignore or artist.completed:
                continue
            timer = artist.timer or self.global_timer
            if timer and self._due(artist.id, timer):
                self._add(DownloadTask(artist.id, task_type=TaskType.SCHEDULED))

    def _due(self, artist_id: str, timer: Dict) -> bool:
        now = datetime.now()
        if artist_id not in self._next_runs:
            self._next_runs[artist_id] = self._next(timer, now)
            return False
        if now >= self._next_runs[artist_id]:
            self._next_runs[artist_id] = self._next(timer, now)
            return True
        return False

    @staticmethod
    def _next(timer: Dict, frm: datetime) -> datetime:
        hour, minute = map(int, timer.get("time", "00:00").split(":"))
        nxt = frm.replace(hour=hour, minute=minute, second=0, microsecond=0)
        kind = timer.get("type", "daily")
        if kind == "daily":
            if nxt <= frm:
                nxt += timedelta(days=1)
        elif kind == "weekly":
            days = (timer.get("day", 0) - frm.weekday()) % 7 or 7
            nxt += timedelta(days=days)
        elif kind == "monthly":
            nxt = nxt.replace(day=timer.get("day", 1))
            if nxt <= frm:
                nxt = (nxt.replace(year=frm.year + 1, month=1) if frm.month == 12
                       else nxt.replace(month=frm.month + 1))
        return nxt
