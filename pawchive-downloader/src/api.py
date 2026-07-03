import threading
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

from .logger import Logger


class API:
    """Client for the Pawchive API (https://pawchive.st/api/schema).

    Differences from the kemono API this project descends from:
      * the post list lives at ``/{service}/user/{id}`` (no ``/posts`` suffix)
      * a single post is returned directly, not wrapped in ``{"post": ...}``
      * the profile carries no ``post_count`` -- change detection uses the
        ``updated`` timestamp and pagination runs until a short page
      * files are served from ``file.pawchive.st`` (see ``file_url``)

    Creator/service ids are identical to kemono's, so ids can be reused.
    """

    API_BASE = "https://pawchive.st/api/v1"
    FILE_BASE = "https://file.pawchive.st"
    PAGE_SIZE = 50

    def __init__(self, logger: Logger, config):
        self.logger = logger
        self.config = config
        self.session = requests.Session()
        self.proxies = {'http': config.proxy, 'https': config.proxy} if config.proxy else None
        self.headers = {
            'User-Agent': config.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        self._stop = threading.Event()

    # ==================== Lifecycle ====================

    def stop(self):
        self._stop.set()
        try:
            self.session.close()
        except Exception:
            pass

    def resume(self):
        self._stop.clear()
        self.session = requests.Session()

    def _check_stop(self):
        if self._stop.is_set():
            raise InterruptedError("Request cancelled")

    # ==================== URL helpers ====================

    @classmethod
    def file_url(cls, path: str, name: str = "") -> str:
        """Build a full-file download URL from a post file ``path``.

        e.g. ``/ab/f8/abf8….jpg`` -> ``https://file.pawchive.st/data/ab/f8/….jpg?f=<name>``
        The ``f`` query sets the download filename served by the CDN.
        """
        url = f"{cls.FILE_BASE}/data{path}"
        if name:
            url += f"?f={quote(name)}"
        return url

    # ==================== Raw requests ====================

    def _get_json(self, url: str, timeout: int = None):
        self._check_stop()
        resp = self.session.get(
            url, headers=self.headers, proxies=self.proxies,
            timeout=timeout or self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_profile(self, service: str, user_id: str) -> Dict:
        return self._get_json(f"{self.API_BASE}/{service}/user/{user_id}/profile")

    def get_posts(self, service: str, user_id: str, offset: int = 0) -> List[Dict]:
        url = f"{self.API_BASE}/{service}/user/{user_id}"
        if offset:
            url += f"?o={offset}"
        data = self._get_json(url)
        return data if isinstance(data, list) else []

    def get_post(self, service: str, user_id: str, post_id: str) -> Dict:
        return self._get_json(f"{self.API_BASE}/{service}/user/{user_id}/post/{post_id}")

    # ==================== Retry wrappers ====================

    @staticmethod
    def _is_permanent(e: Exception) -> bool:
        """A 4xx (except 429 rate-limit) is a permanent client error and should
        not be retried; connection/timeout/5xx errors are transient."""
        resp = getattr(e, 'response', None)
        code = getattr(resp, 'status_code', None)
        return code is not None and 400 <= code < 500 and code != 429

    def _retry(self, func, describe: str):
        """Retry transient network errors indefinitely; re-raise permanent ones."""
        while True:
            self._check_stop()
            try:
                return func()
            except InterruptedError:
                raise
            except requests.exceptions.RequestException as e:
                if self._stop.is_set():
                    raise InterruptedError("Request cancelled")
                if self._is_permanent(e):
                    raise
                self.logger.api_network_error(
                    op=describe, error=str(e), retry_in=self.config.retry_delay, level='warning'
                )
                time.sleep(self.config.retry_delay)

    def get_profile_until_success(self, service: str, user_id: str) -> Dict:
        return self._retry(lambda: self.get_profile(service, user_id), f"profile {service}/{user_id}")

    def get_post_until_success(self, service: str, user_id: str, post_id: str) -> Dict:
        return self._retry(lambda: self.get_post(service, user_id, post_id), f"post {post_id}")

    def get_posts_until_success(self, service: str, user_id: str, offset: int = 0) -> List[Dict]:
        return self._retry(lambda: self.get_posts(service, user_id, offset), f"posts o={offset}")

    def get_all_posts(self, service: str, user_id: str) -> List[Dict]:
        """Fetch every post by paging sequentially until a short/empty page.

        Sequential (not concurrent) because the API exposes no total count, so
        we can't know the page count up front.
        """
        all_posts: List[Dict] = []
        offset = 0
        while True:
            self._check_stop()
            batch = self.get_posts_until_success(service, user_id, offset)
            if not batch:
                break
            all_posts.extend(batch)
            if len(batch) < self.PAGE_SIZE:
                break
            offset += self.PAGE_SIZE
        return all_posts

    # ==================== File download ====================

    def download_file(self, url: str, save_path: str, raise_on_error: bool = False,
                      on_progress=None) -> bool:
        """Download ``url`` to ``save_path`` atomically via a ``.tmp`` file.

        If a file already exists with a matching content-length it is skipped;
        on a size mismatch a ``(n)`` suffix is added rather than overwriting.
        """
        temp_path = None
        try:
            self._check_stop()
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(path.suffix + '.tmp')
            if temp_path.exists():
                temp_path.unlink()

            resp = self.session.get(
                url, headers=self.headers, proxies=self.proxies,
                timeout=max(60, self.config.request_timeout), stream=True,
            )
            resp.raise_for_status()

            content_length = int(resp.headers.get('content-length', 0) or 0)
            if content_length and path.exists() and path.stat().st_size == content_length:
                return True  # already downloaded

            downloaded = 0
            with open(temp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if self._stop.is_set():
                        raise InterruptedError("Download cancelled")
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress:
                            on_progress(path.name, downloaded, content_length)

            final_path = path
            if final_path.exists():
                counter = 1
                while final_path.exists():
                    final_path = path.parent / f"{path.stem} ({counter}){path.suffix}"
                    counter += 1
            temp_path.rename(final_path)
            return True

        except InterruptedError:
            self._cleanup(temp_path)
            if raise_on_error:
                raise
            return False
        except Exception:
            self._cleanup(temp_path)
            if raise_on_error:
                raise
            return False

    @staticmethod
    def _cleanup(temp_path):
        try:
            if temp_path and temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass

    def download_file_until_success(self, url: str, save_path: str, on_progress=None) -> bool:
        return self._retry(
            lambda: self.download_file(url, save_path, raise_on_error=True, on_progress=on_progress),
            f"download {Path(save_path).name}",
        )
