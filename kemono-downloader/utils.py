#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility Functions
"""

import os
import re
import time
from datetime import datetime
from typing import Tuple, Callable, Any
from functools import wraps
from urllib.parse import urlparse, unquote

import requests

from config import (
    ARTIST_FOLDER_NAME_FORMAT,
    POST_FOLDER_NAME_FORMAT,
    DATE_FORMAT,
    FILE_NAME_FORMAT,
    MAX_RETRIES,
    RETRY_DELAY_BASE
)


# ============================================================================
# Constants
# ============================================================================

SEPARATOR = '=' * 60
SUB_SEPARATOR = '─' * 60


# ============================================================================
# Decorators
# ============================================================================

def retry_on_error(max_retries: int = MAX_RETRIES,
                   base_delay: int = RETRY_DELAY_BASE,
                   exponential_backoff: bool = True,
                   retry_status: list = None):
    """Decorator for automatic retry on timeout, connection, and HTTP errors"""
    if retry_status is None:
        retry_status = [403, 429, 500, 502, 503, 504]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        wait = base_delay ** attempt if exponential_backoff else base_delay * attempt
                        print(f"  Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait)
                    
                    return func(*args, **kwargs)
                    
                except (requests.Timeout, requests.ConnectionError) as e:
                    if attempt == max_retries - 1:
                        raise Exception(f"Network error after {max_retries} attempts: {e}")
                    print(f"  ⚠ {type(e).__name__}, will retry...")
                        
                except requests.HTTPError as e:
                    status = getattr(e.response, 'status_code', None)
                    if status in retry_status and attempt < max_retries - 1:
                        print(f"  ⚠ HTTP {status} error, will retry...")
                    else:
                        raise Exception(f"HTTP {status} error: {e}")
                        
                except Exception as e:
                    raise Exception(f"Unexpected error: {e}")
            
        return wrapper
    return decorator


# ============================================================================
# URL Parsing
# ============================================================================

def parse_post_url(url: str) -> Tuple[str, str, str]:
    """Parse post URL and extract (service, user_id, post_id)"""
    try:
        parts = urlparse(url).path.strip('/').split('/')
        
        if len(parts) < 5 or parts[1] != 'user' or parts[3] != 'post':
            raise ValueError("Invalid URL format")
        
        return parts[0], parts[2], parts[4]
    
    except Exception as e:
        raise ValueError(
            f"Invalid Post URL: {url}\n"
            f"Expected: https://kemono.cr/service/user/USER_ID/post/POST_ID"
        ) from e


def parse_profile_url(url: str) -> Tuple[str, str]:
    """Parse profile URL and extract (service, user_id)"""
    try:
        parts = urlparse(url).path.strip('/').split('/')
        
        if len(parts) < 3 or parts[1] != 'user':
            raise ValueError("Invalid URL format")
        
        return parts[0], parts[2]
    
    except Exception as e:
        raise ValueError(
            f"Invalid Profile URL: {url}\n"
            f"Expected: https://kemono.cr/service/user/USER_ID"
        ) from e


# ============================================================================
# String Sanitization
# ============================================================================

def sanitize_filename(filename: str, max_bytes: int = 50) -> str:
    """Sanitize filename by removing illegal characters and limiting length"""
    if not filename:
        return "unknown"
    
    try:
        filename = unquote(filename, encoding='utf-8')
    except:
        pass
    
    sanitized = re.sub(r'[<>:"/\\|?*.]', '_', filename)
    sanitized = re.sub(r'[_\s]+', '_', sanitized).strip('_ ')
    
    while sanitized and len(sanitized.encode('utf-8')) > max_bytes:
        sanitized = sanitized[:-1]
    
    return sanitized or "unknown"


def sanitize_folder_name(name: str) -> str:
    """Sanitize folder name by replacing path separators"""
    return name.replace('/', '_').replace('\\', '_') if name else "unknown"


def _format_date(date_str: str) -> str:
    """Format ISO date string to configured format"""
    if not date_str:
        return ''
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime(DATE_FORMAT)
    except:
        return date_str.split('T')[0]


# ============================================================================
# Name Formatting
# ============================================================================

def format_artist_folder_name(name: str, service: str, user_id: str,
                              indexed: str = '', updated: str = '', public_id: str = '') -> str:
    """Format artist folder name based on configuration"""
    try:
        safe_name = sanitize_folder_name(name or 'unknown')
        safe_service = sanitize_folder_name(service or 'unknown')
        safe_id = sanitize_folder_name(user_id or 'unknown')
        safe_public_id = sanitize_folder_name(public_id or '')
        
        folder_name = ARTIST_FOLDER_NAME_FORMAT.format(
            id=safe_id,
            name=safe_name,
            service=safe_service,
            indexed=_format_date(indexed),
            updated=_format_date(updated),
            public_id=safe_public_id
        )
        
        folder_name = sanitize_folder_name(folder_name).strip()
        return folder_name or f"{safe_name}-{safe_service}-{safe_id}"
        
    except Exception as e:
        print(f"  Warning: Error formatting artist folder: {e}")
        return f"{sanitize_folder_name(name or 'unknown')}-{sanitize_folder_name(service or 'unknown')}-{sanitize_folder_name(user_id or 'unknown')}"


def format_post_folder_name(post_data: dict) -> str:
    """Format post folder name based on configuration"""
    try:
        post = post_data.get('post', {})
        post_id = str(post.get('id', 'unknown'))
        title = sanitize_filename(post.get('title', '') or 'untitled')
        published = _format_date(post.get('published', ''))
        
        folder_name = POST_FOLDER_NAME_FORMAT.format(
            id=post_id,
            title=title,
            published=published
        )
        
        folder_name = sanitize_folder_name(folder_name).strip()
        return folder_name or post_id
        
    except Exception as e:
        print(f"  Warning: Error formatting post folder: {e}")
        return str(post_data.get('post', {}).get('id', 'unknown'))


def format_file_name(name: str, idx: int) -> str:
    """Format file name based on configuration"""
    try:
        base, ext = os.path.splitext(name) if name else ('', '')
        safe_base = sanitize_filename(base) if base else str(idx)
        
        formatted = FILE_NAME_FORMAT.format(idx=idx, name=safe_base)
        final = f"{formatted}{ext}".strip()
        
        return final or (f"{idx}{ext}" if ext else str(idx))
        
    except Exception as e:
        print(f"  Warning: Error formatting file name: {e}")
        if name:
            base, ext = os.path.splitext(name)
            return f"{idx}-{sanitize_filename(base) if base else idx}{ext}"
        return str(idx)


# ============================================================================
# File Operations
# ============================================================================

def safe_remove_file(file_path: str) -> bool:
    """Safely remove a file, ignoring errors"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except:
        pass
    return False


# ============================================================================
# Data Extraction
# ============================================================================

def extract_file_urls(post_data: dict) -> list:
    """Extract all file URLs from post data"""
    files = []
    
    for item in post_data.get('previews', []):
        if 'server' in item and 'path' in item:
            files.append((item.get('name', ''), f"{item['server']}/data{item['path']}"))
    
    for item in post_data.get('attachments', []):
        if 'server' in item and 'path' in item:
            files.append((item.get('name', ''), f"{item['server']}/data{item['path']}"))
    
    for item in post_data.get('videos', []):
        if 'server' in item and 'path' in item:
            files.append((item.get('name', ''), f"{item['server']}/data{item['path']}"))
    
    return files


# ============================================================================
# Result Handling
# ============================================================================

def create_download_result(total: int = 0, success: int = 0, failed: list = None) -> dict:
    """Create standardized download result dictionary"""
    return {
        'total': total,
        'success': success,
        'failed': failed if failed is not None else []
    }


# ============================================================================
# UI Helpers
# ============================================================================

def print_separator(text: str = '', use_sub: bool = False):
    """Print separator line with optional text"""
    sep = SUB_SEPARATOR if use_sub else SEPARATOR
    if text:
        print(f"\n{sep}")
        print(text)
        print(sep)
    else:
        print(f"\n{sep}")
