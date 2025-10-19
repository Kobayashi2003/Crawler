#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File Download Functions
"""

import os
from typing import Dict
from urllib.parse import urlparse

from tqdm import tqdm

from config import HEADERS
from utils import (
    format_file_name,
    retry_on_error,
    safe_remove_file,
    extract_file_urls,
    create_download_result,
    SEPARATOR
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

def _download_with_progress(response, save_path: str):
    """Download file with progress bar"""
    total_size = int(response.headers.get('content-length', 0))
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    with open(save_path, 'wb') as f:
        if total_size > 0:
            with tqdm(total=total_size, unit='B', unit_scale=True,
                     desc=os.path.basename(save_path)[:30]) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        else:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
            print(f"✓ Download complete: {os.path.basename(save_path)}")


@retry_on_error(max_retries=3, base_delay=2, exponential_backoff=True)
def _perform_download(session, url: str, save_path: str):
    """Perform the actual download with retry"""
    response = session.get(url, stream=True, timeout=60)
    response.raise_for_status()
    _download_with_progress(response, save_path)


def download_file(session, url: str, save_path: str, max_retries: int = 3) -> bool:
    """Download a single file with progress bar and retry mechanism"""
    try:
        if _check_existing_file(session, url, save_path):
            return True
        
        safe_remove_file(save_path)
        _perform_download(session, url, save_path)
        return True
        
    except Exception as e:
        print(f"✗ Download failed {os.path.basename(save_path)}: {e}")
        safe_remove_file(save_path)
        return False


# ============================================================================
# Batch Operations
# ============================================================================

def download_post_files(session, post_data: Dict, save_dir: str) -> Dict:
    """Download all files from a post"""
    os.makedirs(save_dir, exist_ok=True)
    
    files_to_download = extract_file_urls(post_data)
    
    if not files_to_download:
        print("  This post has no files")
        return create_download_result()
    
    results = create_download_result(total=len(files_to_download))
    
    for idx, (name, url) in enumerate(files_to_download, 1):
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
