#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File Download Functions
"""

import os
import time
from typing import Dict
from urllib.parse import urlparse

from tqdm import tqdm

from config import HEADERS, SAVE_SUBSTRING_TO_FILE
from utils import (
    SEPARATOR,
    create_download_result,
    extract_file_urls,
    format_file_name,
    retry_on_error,
    safe_remove_file,
)


# ============================================================================
# File Validation
# ============================================================================

def _check_existing_file(session, url: str, save_path: str) -> bool:
    """Check if file already exists with correct size"""
    if not os.path.exists(save_path):
        return False
    
    existing_size = os.path.getsize(save_path)
    try:
        head_response = session.session.head(url, cookies=session.cookies,
                                             headers=HEADERS, timeout=10)
        expected_size = int(head_response.headers.get('content-length', 0))
        
        if expected_size > 0 and existing_size == expected_size:
            print(f"✓ Skipped (exists): {os.path.basename(save_path)}")
            return True
    except:
        pass
    
    return False


# ============================================================================
# Download Core
# ============================================================================

def _download_with_progress(response, save_path: str, resume_pos: int = 0):
    """Download file with progress bar, append mode if resuming"""
    content_length = int(response.headers.get('content-length', 0))
    total_size = content_length + resume_pos if resume_pos > 0 else content_length
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    write_mode = 'ab' if resume_pos > 0 else 'wb'
    
    with open(save_path, write_mode) as file:
        if total_size > 0:
            _download_with_progress_bar(response, file, total_size, resume_pos, save_path)
        else:
            _download_without_progress_bar(response, file, save_path)


def _download_with_progress_bar(response, file, total_size: int, initial_pos: int, save_path: str):
    """Stream download with tqdm progress bar"""
    filename = os.path.basename(save_path)[:30]
    
    with tqdm(total=total_size, initial=initial_pos, unit='B', 
              unit_scale=True, desc=filename) as progress_bar:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)
                progress_bar.update(len(chunk))


def _download_without_progress_bar(response, file, save_path: str):
    """Stream download without progress bar (unknown file size)"""
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            file.write(chunk)
    
    print(f"✓ Download complete: {os.path.basename(save_path)}")


def _perform_download(session, url: str, save_path: str, resume_pos: int = 0):
    """Execute download with resume support"""
    headers = _prepare_download_headers(resume_pos)
    response = session.get(url, stream=True, timeout=300, headers=headers)
    _validate_response_status(response)
    actual_resume_pos = _check_resume_support(response, resume_pos, save_path)
    _download_with_progress(response, save_path, actual_resume_pos)


def _prepare_download_headers(resume_pos: int) -> dict:
    """Add Range header if resuming download"""
    headers = HEADERS.copy()
    
    if resume_pos > 0:
        headers['Range'] = f'bytes={resume_pos}-'
        print(f"  Resuming from byte {resume_pos:,}")
    
    return headers


def _validate_response_status(response):
    """Ensure response status is 200 (OK) or 206 (Partial Content)"""
    if response.status_code not in [200, 206]:
        response.raise_for_status()


def _check_resume_support(response, resume_pos: int, save_path: str) -> int:
    """Return 0 if server doesn't support resume, otherwise return resume_pos"""
    if resume_pos > 0 and response.status_code == 200:
        print(f"  Server doesn't support resume, restarting download")
        safe_remove_file(save_path)
        return 0
    
    return resume_pos


def download_file(session, url: str, save_path: str, max_retries: int = 5) -> bool:
    """Download file with retry and resume support"""
    try:
        if _check_existing_file(session, url, save_path):
            return True
        
        return _download_with_retry(session, url, save_path, max_retries)
        
    except Exception as e:
        _handle_download_failure(save_path, e)
        return False


def _download_with_retry(session, url: str, save_path: str, max_retries: int) -> bool:
    """Retry download up to max_retries times with exponential backoff"""
    for attempt in range(max_retries):
        try:
            resume_pos = _get_resume_position(save_path)
            _perform_download(session, url, save_path, resume_pos)
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                _handle_retry(e, attempt, max_retries)
            else:
                raise


def _get_resume_position(save_path: str) -> int:
    """Return file size if exists, otherwise 0"""
    if not os.path.exists(save_path):
        return 0
    
    file_size = os.path.getsize(save_path)
    
    if file_size > 0:
        print(f"  Found partial file ({file_size:,} bytes)")
    
    return file_size


def _handle_retry(error: Exception, attempt: int, max_retries: int):
    """Wait with exponential backoff before retry"""
    wait_time = 2 ** (attempt + 1)  # 2, 4, 8, 16, 32 seconds
    
    print(f"  ⚠ Download interrupted: {type(error).__name__}")
    print(f"  Retrying in {wait_time}s... (attempt {attempt + 2}/{max_retries})")
    
    time.sleep(wait_time)


def _handle_download_failure(save_path: str, error: Exception):
    """Print failure message and keep partial file"""
    filename = os.path.basename(save_path)
    
    print(f"✗ Download failed {filename}: {error}")
    print(f"  Partial file kept at: {save_path}")


# ============================================================================
# Batch Operations
# ============================================================================

def _save_content_to_file(post_data: Dict, save_dir: str):
    """Save post content to content.txt if enabled
    """
    if not SAVE_SUBSTRING_TO_FILE:
        return
    
    post = post_data.get('post', {})
    content = post.get('content', '').strip()
    
    if not content:
        return
    
    try:
        content_file = os.path.join(save_dir, 'content.txt')
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Saved content to content.txt")
    except Exception as e:
        print(f"  ⚠ Failed to save content: {e}")


def download_post_files(session, post_data: Dict, save_dir: str) -> Dict:
    """Download all files from a post"""
    os.makedirs(save_dir, exist_ok=True)
    
    # Save substring to content.txt if enabled
    _save_content_to_file(post_data, save_dir)
    
    files_to_download = extract_file_urls(post_data)
    
    if not files_to_download:
        print("  This post has no files")
        return create_download_result()
    
    results = create_download_result(total=len(files_to_download))
    
    for idx, (name, url) in enumerate(files_to_download):
        if not name:
            url_ext = os.path.splitext(urlparse(url).path)[1]
            name = f"file{url_ext}" if url_ext else "file"
        
        filename = format_file_name(name, idx)
        save_path = os.path.join(save_dir, filename)
        
        if download_file(session, url, save_path):
            results['success'] += 1
        else:
            results['failed'].append({'url': url, 'name': name, 'idx': idx, 'save_path': save_path})
    
    return results


# ============================================================================
# Retry Operations
# ============================================================================

def retry_failed_downloads(session, failed_list: list) -> Dict:
    """Retry failed downloads"""
    if not failed_list:
        return create_download_result()
    
    print(f"\n{SEPARATOR}")
    print(f"Retrying {len(failed_list)} failed downloads...")
    print(SEPARATOR)
    
    results = create_download_result(total=len(failed_list))
    
    for item in failed_list:
        print(f"\nRetrying: {os.path.basename(item['save_path'])}")
        if download_file(session, item['url'], item['save_path']):
            results['success'] += 1
        else:
            results['failed'].append(item)
    
    return results
