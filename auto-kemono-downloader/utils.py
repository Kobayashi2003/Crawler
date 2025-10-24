#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility Functions
"""

import os
import time
from datetime import datetime
from functools import wraps
from typing import Any, Callable
from urllib.parse import unquote, urlparse

import requests


# ============================================================================
# Decorators
# ============================================================================

def retry_on_error(max_retries: int = 10, base_delay: int = 5,
                   exponential_backoff: bool = True, retry_status: list = None):
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
# String Processing
# ============================================================================

def sanitize_path_component(text: str, char_map: dict) -> str:
    """Sanitize path component by replacing illegal characters"""
    if not text:
        return "unknown"

    try:
        text = unquote(text, encoding='utf-8')
    except:
        pass

    result = text
    for char, replacement in char_map.items():
        if replacement is not None:
            result = result.replace(char, replacement)

    return result or "unknown"


def format_date(date_str: str, date_format: str) -> str:
    """Format ISO date string to specified format"""
    if not date_str:
        return ''
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime(date_format)
    except:
        return date_str.split('T')[0]


# ============================================================================
# URL Parsing
# ============================================================================

def parse_artist_url(url: str) -> tuple:
    """Parse artist URL and extract (service, user_id)"""
    try:
        parsed = urlparse(url)
        parts = parsed.path.strip('/').split('/')

        # Expected format: /service/user/user_id
        if len(parts) >= 3 and parts[1] == 'user':
            service = parts[0]
            user_id = parts[2]
            return service, user_id
        else:
            raise ValueError("Invalid URL format")
    except Exception as e:
        raise ValueError(
            f"Invalid artist URL: {url}\n"
            f"Expected format: https://kemono.cr/service/user/USER_ID\n"
            f"Example: https://kemono.cr/fanbox/user/25877697"
        ) from e


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
# Naming Formatters
# ============================================================================

def format_artist_folder_name(artist_data: dict, config: dict) -> str:
    """Format artist folder name based on configuration"""
    try:
        char_map = config.get('char_replacement', {})
        
        # Use alias if available, otherwise use real name
        display_name = artist_data.get('alias') if artist_data.get('alias') else artist_data['name']
        safe_name = sanitize_path_component(display_name, char_map)
        safe_service = sanitize_path_component(artist_data['service'], char_map)
        safe_id = sanitize_path_component(artist_data['user_id'], char_map)
        
        template = config.get('artist_folder_format', '{name}')
        folder_name = template.format(
            name=safe_name,
            service=safe_service,
            id=safe_id
        )
        
        folder_name = sanitize_path_component(folder_name, char_map).strip()
        return folder_name or f"{safe_name}-{safe_service}-{safe_id}"
        
    except Exception as e:
        print(f"  Warning: Error formatting artist folder: {e}")
        display_name = artist_data.get('alias') if artist_data.get('alias') else artist_data['name']
        return sanitize_path_component(display_name, {})


def format_post_folder_name(post_data: dict, config: dict) -> str:
    """Format post folder name based on configuration"""
    try:
        char_map = config.get('char_replacement', {})
        date_format = config.get('date_format', '%Y.%m.%d')
        
        post = post_data.get('post', {})
        post_id = str(post.get('id', 'unknown'))
        title = sanitize_path_component(post.get('title', '') or 'untitled', char_map)
        published = format_date(post.get('published', ''), date_format)
        
        template = config.get('post_folder_format', '[{published}] {title}')
        folder_name = template.format(
            id=post_id,
            title=title,
            published=published
        )
        
        folder_name = sanitize_path_component(folder_name, char_map).strip()
        return folder_name or post_id
        
    except Exception as e:
        print(f"  Warning: Error formatting post folder: {e}")
        return str(post_data.get('post', {}).get('id', 'unknown'))


def format_file_name(name: str, idx: int, config: dict) -> str:
    """Format file name based on configuration"""
    try:
        base, ext = os.path.splitext(name) if name else ('', '')
        
        # Check if we should rename this file
        rename_images_only = config.get('rename_images_only', True)
        image_extensions = set(config.get('image_extensions', ['.jpg', '.jpeg', '.png', '.gif', '.webp']))
        
        if rename_images_only and ext.lower() not in image_extensions:
            # Keep original name for non-image files
            return name if name else str(idx)
        
        char_map = config.get('char_replacement', {})
        safe_base = sanitize_path_component(base, char_map) if base else str(idx)
        
        file_name_format = config.get('file_name_format', '{idx}')
        formatted = file_name_format.format(idx=idx, name=safe_base)
        final = f"{formatted}{ext}".strip()
        
        return final or (f"{idx}{ext}" if ext else str(idx))
        
    except Exception as e:
        print(f"  Warning: Error formatting file name: {e}")
        if name:
            base, ext = os.path.splitext(name)
            return f"{idx}-{sanitize_path_component(base, {}) if base else idx}{ext}"
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
