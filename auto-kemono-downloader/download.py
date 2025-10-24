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

from logger import DownloadLogger
from session import HEADERS
from utils import extract_file_urls, format_file_name, safe_remove_file


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
    """Download file with progress bar"""
    content_length = int(response.headers.get('content-length', 0))
    total_size = content_length + resume_pos if resume_pos > 0 else content_length
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    write_mode = 'ab' if resume_pos > 0 else 'wb'
    
    with open(save_path, write_mode) as file:
        if total_size > 0:
            filename = os.path.basename(save_path)[:30]
            with tqdm(total=total_size, initial=resume_pos, unit='B', 
                      unit_scale=True, desc=filename) as progress_bar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        progress_bar.update(len(chunk))
        else:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
            print(f"✓ Download complete: {os.path.basename(save_path)}")


def _perform_download(session, url: str, save_path: str, resume_pos: int = 0):
    """Execute download with resume support"""
    headers = HEADERS.copy()
    if resume_pos > 0:
        headers['Range'] = f'bytes={resume_pos}-'
        print(f"  Resuming from byte {resume_pos:,}")
    
    response = session.get(url, stream=True, timeout=300, headers=headers)
    
    if response.status_code not in [200, 206]:
        response.raise_for_status()
    
    # Check if server supports resume
    if resume_pos > 0 and response.status_code == 200:
        print(f"  Server doesn't support resume, restarting download")
        safe_remove_file(save_path)
        resume_pos = 0
    
    _download_with_progress(response, save_path, resume_pos)


def download_file(session, url: str, save_path: str, max_retries: int = 5) -> bool:
    """Download file with retry and resume support"""
    try:
        if _check_existing_file(session, url, save_path):
            return True
        
        for attempt in range(max_retries):
            try:
                resume_pos = os.path.getsize(save_path) if os.path.exists(save_path) else 0
                if resume_pos > 0:
                    print(f"  Found partial file ({resume_pos:,} bytes)")
                
                _perform_download(session, url, save_path, resume_pos)
                return True
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** (attempt + 1)
                    print(f"  ⚠ Download interrupted: {type(e).__name__}")
                    print(f"  Retrying in {wait_time}s... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise
        
    except Exception as e:
        filename = os.path.basename(save_path)
        print(f"✗ Download failed {filename}: {e}")
        print(f"  Partial file kept at: {save_path}")
        return False


# ============================================================================
# Batch Operations
# ============================================================================

def download_post_files(session, post_data: Dict, save_dir: str, 
                       config: Dict, save_content: bool = True, 
                       logger: DownloadLogger = None) -> Dict:
    """Download all files from a post"""
    os.makedirs(save_dir, exist_ok=True)
    
    if logger is None:
        logger = DownloadLogger()
    
    # Save content to file if enabled
    if save_content:
        post = post_data.get('post', {})
        content = post.get('content', '').strip()
        if content:
            try:
                content_file = os.path.join(save_dir, 'content.txt')
                with open(content_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  ✓ Saved content to content.txt")
            except Exception as e:
                print(f"  ⚠ Failed to save content: {e}")
    
    files_to_download = extract_file_urls(post_data)
    
    if not files_to_download:
        print("  This post has no files")
        return {'total': 0, 'success': 0, 'failed': []}
    
    results = {'total': len(files_to_download), 'success': 0, 'failed': []}
    
    for idx, (name, url) in enumerate(files_to_download):
        if not name:
            url_ext = os.path.splitext(urlparse(url).path)[1]
            name = f"file{url_ext}" if url_ext else "file"
        
        # Format file name using configuration
        formatted_name = format_file_name(name, idx, config)
        save_path = os.path.join(save_dir, formatted_name)
        
        success = download_file(session, url, save_path)
        logger.log_file_download(formatted_name, success)
        
        if success:
            results['success'] += 1
        else:
            results['failed'].append({'url': url, 'name': formatted_name, 'save_path': save_path})
    
    return results
