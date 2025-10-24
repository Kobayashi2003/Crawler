#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Logger for Download Operations
"""

import os
from datetime import datetime


class DownloadLogger:
    """Simple logger for download operations"""
    
    def __init__(self, log_file: str = "download.log"):
        """Initialize logger"""
        self.log_file = log_file
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Ensure log file exists"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"# Download Log - Created {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    def _write_log(self, message: str):
        """Write message to log file"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"Warning: Failed to write log: {e}")
    
    def log_artist_check(self, artist_name: str, artist_id: str):
        """Log artist check start"""
        self._write_log(f"Checking artist: {artist_name} (ID: {artist_id})")
    
    def log_posts_found(self, artist_name: str, count: int):
        """Log number of new posts found"""
        self._write_log(f"  Found {count} new posts for {artist_name}")
    
    def log_post_download_start(self, artist_name: str, post_title: str, post_id: str):
        """Log post download start"""
        self._write_log(f"  Downloading post: {post_title} (ID: {post_id}) from {artist_name}")
    
    def log_post_filtered(self, post_title: str):
        """Log filtered post"""
        self._write_log(f"  Skipped (filtered): {post_title}")
    
    def log_file_download(self, filename: str, success: bool):
        """Log file download result"""
        status = "✓" if success else "✗"
        self._write_log(f"    {status} File: {filename}")
    
    def log_post_complete(self, post_title: str, files_downloaded: int, files_failed: int):
        """Log post download completion"""
        self._write_log(f"  Completed: {post_title} - {files_downloaded} files downloaded, {files_failed} failed")
    
    def log_artist_summary(self, artist_name: str, posts_checked: int, 
                          posts_downloaded: int, files_downloaded: int, files_failed: int):
        """Log artist check summary"""
        self._write_log(
            f"Summary for {artist_name}: "
            f"{posts_checked} posts checked, {posts_downloaded} posts downloaded, "
            f"{files_downloaded} files downloaded, {files_failed} files failed"
        )
    
    def log_error(self, context: str, error: str):
        """Log error"""
        self._write_log(f"ERROR in {context}: {error}")
