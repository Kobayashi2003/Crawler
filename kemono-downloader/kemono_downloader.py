#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kemono Downloader - Simplified Kemono content download tool
Supports 4 download modes: single post, all posts, specific page, page range
"""

import os
import re
import sys
import time
from typing import Dict, List, Tuple 
from urllib.parse import urlparse, unquote

import requests
from tqdm import tqdm

# ============================================================================
# Constants & Configuration
# ============================================================================

# Domain configuration
KEMONO_DOMAIN = "kemono.cr"
BASE_API_URL = f"https://{KEMONO_DOMAIN}/api/v1"
BASE_SERVER = f"https://{KEMONO_DOMAIN}"

# HTTP configuration
INIT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'DNT': '1',
    'Sec-GPC': '1',
    'Upgrade-Insecure-Requests': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Priority': 'u=0, i',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
    'Accept': 'text/css',
    'Accept-Language': 'en-US,en;q=0.5',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}

# Download configuration
POSTS_PER_PAGE = 50
MAX_RETRIES = 3
RETRY_DELAY_BASE = 5  # seconds, for exponential backoff

# Post folder naming configuration
# Available variables: {id}, {title}, {published}
# Examples:
#   "{id}" - Just the post ID (default)
#   "{published}_{title}" - Date and title
#   "{published}_{id}_{title}" - Date, ID, and title
#   "[{id}] {title}" - ID in brackets with title
POST_FOLDER_NAME_FORMAT = "{id}"

# Date format for {published} variable (uses Python strftime format)
# Examples:
#   "%Y-%m-%d" - 2025-01-15 (default)
#   "%Y%m%d" - 20250115
#   "%Y-%m-%d_%H-%M-%S" - 2025-01-15_14-30-00
#   "%m-%d-%Y" - 01-15-2025
PUBLISHED_DATE_FORMAT = "%Y-%m-%d"


# ============================================================================
# Session Management
# ============================================================================

class KemonoSession:
    """Manage Kemono session and cookies"""
    
    def __init__(self):
        """Initialize session"""
        self.session = requests.Session()
        self.cookies = {}
        self._initialize_session()
    
    def _initialize_session(self):
        """Initialize session and obtain cookies"""
        try:
            response = self.session.get(BASE_SERVER, headers=INIT_HEADERS, timeout=10)
            self.cookies = response.cookies.get_dict()
            print(f"Session initialized successfully, obtained {len(self.cookies)} cookies")
        except Exception as e:
            print(f"Warning: Session initialization failed: {e}")
            print("Will continue, but may encounter access restrictions")
    
    def get(self, url: str, **kwargs):
        """GET request with cookies"""
        if 'cookies' not in kwargs:
            kwargs['cookies'] = self.cookies
        if 'headers' not in kwargs:
            kwargs['headers'] = HEADERS
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30
        return self.session.get(url, **kwargs)


# ============================================================================
# Helper Functions - URL Parsing
# ============================================================================

def parse_post_url(url: str) -> Tuple[str, str, str]:
    """
    Parse post URL and extract service, user_id, post_id
    
    Args:
        url: Kemono post URL (e.g., https://kemono.cr/fanbox/user/12345/post/67890)
        
    Returns:
        (service, user_id, post_id)
        
    Raises:
        ValueError: Invalid URL format
    """
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        
        # Expected format: service/user/user_id/post/post_id
        if len(path_parts) < 5 or path_parts[1] != 'user' or path_parts[3] != 'post':
            raise ValueError("Invalid URL format")
        
        service = path_parts[0]
        user_id = path_parts[2]
        post_id = path_parts[4]
        
        return service, user_id, post_id
    
    except Exception as e:
        raise ValueError(
            f"Unable to parse Post URL: {url}\n"
            f"Correct format: https://kemono.cr/service/user/user_id/post/post_id\n"
            f"Error: {e}"
        )


def parse_profile_url(url: str) -> Tuple[str, str]:
    """
    Parse profile URL and extract service and user_id
    
    Args:
        url: Kemono profile URL (e.g., https://kemono.cr/fanbox/user/12345)
        
    Returns:
        (service, user_id)
        
    Raises:
        ValueError: Invalid URL format
    """
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        
        # Expected format: service/user/user_id
        if len(path_parts) < 3 or path_parts[1] != 'user':
            raise ValueError("Invalid URL format")
        
        service = path_parts[0]
        user_id = path_parts[2]
        
        return service, user_id
    
    except Exception as e:
        raise ValueError(
            f"Unable to parse Profile URL: {url}\n"
            f"Correct format: https://kemono.cr/service/user/user_id\n"
            f"Error: {e}"
        )


# ============================================================================
# Helper Functions - Filename Sanitization
# ============================================================================

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing illegal characters
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized safe filename
    """
    if not filename:
        return "unknown"
    
    # Try URL decoding
    try:
        filename = unquote(filename, encoding='utf-8')
    except:
        pass
    
    # Remove illegal characters <>:"/\|?*.
    sanitized = re.sub(r'[<>:"/\\|?*.]', '_', filename)
    
    # Replace multiple consecutive underscores or spaces with single underscore
    sanitized = re.sub(r'[_\s]+', '_', sanitized)
    
    # Strip leading/trailing underscores and spaces
    sanitized = sanitized.strip('_ ')
    
    # Limit length (50 bytes in UTF-8 encoding)
    if len(sanitized.encode('utf-8')) > 50:
        while len(sanitized.encode('utf-8')) > 50 and sanitized:
            sanitized = sanitized[:-1]
    
    return sanitized if sanitized else "unknown"


def sanitize_folder_name(name: str) -> str:
    """
    Sanitize folder name
    
    Args:
        name: Original folder name
        
    Returns:
        Sanitized folder name
    """
    if not name:
        return "unknown"
    
    return name.replace('/', '_').replace('\\', '_')


def get_artist_dir(name: str, service: str, user_id: str) -> str:
    """
    Generate standardized artist directory name
    
    Args:
        name: Artist name
        service: Service name
        user_id: User ID
        
    Returns:
        Formatted directory name: name-service-user_id
    """
    safe_name = sanitize_folder_name(name)
    safe_service = sanitize_folder_name(service)
    safe_user_id = sanitize_folder_name(user_id)
    
    return f"{safe_name}-{safe_service}-{safe_user_id}"


def format_post_folder_name(post_data: Dict) -> str:
    """
    Format post folder name based on POST_FOLDER_NAME_FORMAT configuration
    
    Args:
        post_data: Post data dictionary containing 'post' key with id, title, published
        
    Returns:
        Formatted folder name
    """
    try:
        # Extract post information
        post = post_data.get('post', {})
        post_id = str(post.get('id', 'unknown'))
        title = post.get('title', '')
        published_str = post.get('published', '')
        
        # Sanitize title
        safe_title = sanitize_filename(title) if title else 'untitled'
        
        # Format published date if available
        published_formatted = ''
        if published_str:
            try:
                # Parse ISO format datetime: "2025-10-03T23:36:18"
                from datetime import datetime
                dt = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                published_formatted = dt.strftime(PUBLISHED_DATE_FORMAT)
            except:
                # If parsing fails, use the date part only
                published_formatted = published_str.split('T')[0]
        
        # Format the folder name using the template
        folder_name = POST_FOLDER_NAME_FORMAT.format(
            id=post_id,
            title=safe_title,
            published=published_formatted
        )
        
        # Final sanitization to ensure folder name is safe
        folder_name = sanitize_folder_name(folder_name)
        
        # Fallback to post_id if formatting results in empty string
        if not folder_name or folder_name.strip() == '':
            folder_name = post_id
        
        return folder_name
        
    except Exception as e:
        # If any error occurs, fallback to post_id
        print(f"  Warning: Error formatting folder name: {e}")
        post_id = str(post_data.get('post', {}).get('id', 'unknown'))
        return post_id


# ============================================================================
# API Functions
# ============================================================================

def fetch_user_profile(session: KemonoSession, service: str, user_id: str) -> Dict:
    """
    Fetch user profile information
    
    Args:
        session: KemonoSession instance
        service: Service name (e.g., fanbox, patreon, etc.)
        user_id: User ID
        
    Returns:
        User profile data dictionary
        
    Raises:
        requests.HTTPError: API request failed
    """
    url = f"{BASE_API_URL}/{service}/user/{user_id}/profile"
    
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        raise Exception(f"Failed to fetch user profile: {e}")
    except Exception as e:
        raise Exception(f"Error occurred while fetching user profile: {e}")


def fetch_post(session: KemonoSession, service: str, user_id: str, post_id: str) -> Dict:
    """
    Fetch detailed information for a single post with retry mechanism
    
    Args:
        session: KemonoSession instance
        service: Service name
        user_id: User ID
        post_id: Post ID
        
    Returns:
        Post detailed data dictionary
        
    Raises:
        requests.HTTPError: API request failed
    """
    url = f"{BASE_API_URL}/{service}/user/{user_id}/post/{post_id}"
    
    # Implement retry logic
    for retry in range(MAX_RETRIES):
        try:
            time.sleep(1)  # Delay before request
            response = session.get(url)
            
            # If 403 error and retries remaining, retry
            if response.status_code == 403 and retry < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY_BASE ** (retry + 1)
                print(f"Encountered 403 error, retrying in {wait_time}s... (attempt {retry + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response.json()
            
        except requests.HTTPError as e:
            if retry == MAX_RETRIES - 1:
                raise Exception(f"Failed to fetch post (retried {MAX_RETRIES} times): {e}")
        except Exception as e:
            if retry == MAX_RETRIES - 1:
                raise Exception(f"Error occurred while fetching post: {e}")
    
    raise Exception(f"Failed to fetch post: exceeded maximum retries")


def fetch_posts_page(session: KemonoSession, service: str, user_id: str, offset: int = 0) -> List[Dict]:
    """
    Fetch posts list for a specific page
    
    Args:
        session: KemonoSession instance
        service: Service name
        user_id: User ID
        offset: Page offset (0, 50, 100, ...)
        
    Returns:
        List of post summaries
        
    Raises:
        requests.HTTPError: API request failed
    """
    url = f"{BASE_API_URL}/{service}/user/{user_id}/posts"
    if offset > 0:
        url += f"?o={offset}"
    
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        raise Exception(f"Failed to fetch posts list (offset={offset}): {e}")
    except Exception as e:
        raise Exception(f"Error occurred while fetching posts list: {e}")


# ============================================================================
# File Download Functions
# ============================================================================

def download_file(session: KemonoSession, url: str, save_path: str) -> bool:
    """
    Download a single file with progress bar
    
    Args:
        session: KemonoSession instance
        url: File URL
        save_path: Save path
        
    Returns:
        True if successful, False if failed
    """
    try:
        # Check if file already exists
        if os.path.exists(save_path):
            existing_size = os.path.getsize(save_path)
            
            # Try to get expected file size
            try:
                head_response = session.session.head(url, cookies=session.cookies, 
                                                     headers=HEADERS, timeout=10)
                expected_size = int(head_response.headers.get('content-length', 0))
                
                if expected_size > 0 and existing_size == expected_size:
                    print(f"✓ Skipped (exists): {os.path.basename(save_path)}")
                    return True
            except:
                pass  # If HEAD request fails, continue downloading
        
        # Stream download
        response = session.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Download file and show progress
        with open(save_path, 'wb') as f:
            if total_size > 0:
                with tqdm(total=total_size, unit='B', unit_scale=True, 
                         desc=os.path.basename(save_path)[:30]) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            else:
                # If no content-length, download directly
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                print(f"✓ Download complete: {os.path.basename(save_path)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Download failed {os.path.basename(save_path)}: {e}")
        return False


def download_post_files(session: KemonoSession, post_data: Dict, save_dir: str) -> Dict:
    """
    Download all files from a post
    
    Args:
        session: KemonoSession instance
        post_data: Post data returned from API
        save_dir: Save directory
        
    Returns:
        Download statistics dictionary {'total': int, 'success': int, 'failed': list}
    """
    os.makedirs(save_dir, exist_ok=True)
    
    # Collect all file URLs
    files_to_download = []
    
    # Attachments
    for attach in post_data.get('attachments', []):
        if 'server' in attach and 'path' in attach:
            url = f"{attach['server']}/data{attach['path']}"
            name = attach.get('name', '')
            files_to_download.append((name, url))
    
    # Videos
    for video in post_data.get('videos', []):
        if 'server' in video and 'path' in video:
            url = f"{video['server']}/data{video['path']}"
            name = video.get('name', '')
            files_to_download.append((name, url))
    
    # Previews (images)
    for preview in post_data.get('previews', []):
        if 'server' in preview and 'path' in preview:
            url = f"{preview['server']}/data{preview['path']}"
            name = preview.get('name', '')
            files_to_download.append((name, url))
    
    # Download files
    results = {'total': len(files_to_download), 'success': 0, 'failed': []}
    
    if not files_to_download:
        print("  This post has no files")
        return results
    
    for idx, (name, url) in enumerate(files_to_download, 1):
        # Generate filename
        if name:
            ext = os.path.splitext(name)[1]
        else:
            ext = os.path.splitext(urlparse(url).path)[1]
        
        if not ext:
            ext = '.bin'
        
        # Handle .jpeg extension
        if ext.lower() == '.jpeg':
            ext = '.jpg'
        
        safe_name = sanitize_filename(name) if name else str(idx)
        filename = f"{idx}-{safe_name}{ext}"
        save_path = os.path.join(save_dir, filename)
        
        if download_file(session, url, save_path):
            results['success'] += 1
        else:
            results['failed'].append(url)
    
    return results


# ============================================================================
# Core Download Logic
# ============================================================================

def download_single_post(session: KemonoSession, post_url: str):
    """
    Download a single post
    
    Args:
        session: KemonoSession instance
        post_url: Post URL
    """
    print(f"\n{'='*60}")
    print(f"Download Single Post")
    print(f"{'='*60}")
    print(f"URL: {post_url}")
    
    try:
        # Parse URL
        service, user_id, post_id = parse_post_url(post_url)
        print(f"Service: {service}, User ID: {user_id}, Post ID: {post_id}")
        
        # Get user information
        print("\nFetching user information...")
        profile = fetch_user_profile(session, service, user_id)
        artist_name = profile['name']
        print(f"Artist: {artist_name}")
        
        # Get post data
        print(f"\nFetching post data...")
        post_data = fetch_post(session, service, user_id, post_id)
        post_title = post_data.get('post', {}).get('title', post_id)
        print(f"Post title: {post_title}")
        
        # Format post folder name
        post_folder_name = format_post_folder_name(post_data)
        
        # Create directory
        artist_dir = get_artist_dir(artist_name, service, user_id)
        post_dir = os.path.join('kemono', artist_dir, 'posts', post_folder_name)
        
        # Download files
        print(f"\nDownloading files to: {post_dir}")
        results = download_post_files(session, post_data, post_dir)
        
        # Display results
        print(f"\n{'='*60}")
        print(f"Download complete!")
        print(f"Success: {results['success']}/{results['total']} files")
        if results['failed']:
            print(f"Failed: {len(results['failed'])} files")
            for failed_url in results['failed']:
                print(f"  - {failed_url}")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


def download_all_posts(session: KemonoSession, profile_url: str):
    """
    Download all posts from a profile
    
    Args:
        session: KemonoSession instance
        profile_url: Profile URL
    """
    print(f"\n{'='*60}")
    print(f"Download All Posts")
    print(f"{'='*60}")
    
    try:
        # Parse URL
        service, user_id = parse_profile_url(profile_url)
        
        # Get profile information
        print("\nFetching profile information...")
        profile = fetch_user_profile(session, service, user_id)
        
        total_posts = profile['post_count']
        artist_name = profile['name']
        
        print(f"Artist: {artist_name}")
        print(f"Total posts: {total_posts}")
        
        if total_posts == 0:
            print("This artist has no posts")
            return
        
        # Calculate total pages
        total_pages = (total_posts + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE
        print(f"Total pages: {total_pages}")
        
        artist_dir = get_artist_dir(artist_name, service, user_id)
        
        total_success = 0
        total_failed = 0
        
        # Iterate through all pages
        for page_num in range(total_pages):
            offset = page_num * POSTS_PER_PAGE
            print(f"\n{'─'*60}")
            print(f"Processing page {page_num + 1}/{total_pages} (offset: {offset})")
            print(f"{'─'*60}")
            
            try:
                posts = fetch_posts_page(session, service, user_id, offset)
                print(f"Retrieved {len(posts)} posts")
                
                for idx, post_summary in enumerate(posts, 1):
                    post_id = post_summary['id']
                    print(f"\n[{idx}/{len(posts)}] Processing post: {post_id}")
                    
                    try:
                        # Get complete post data
                        post_data = fetch_post(session, service, user_id, post_id)
                        
                        # Format post folder name
                        post_folder_name = format_post_folder_name(post_data)
                        post_dir = os.path.join('kemono', artist_dir, 'posts', post_folder_name)
                        
                        # Download files
                        results = download_post_files(session, post_data, post_dir)
                        print(f"  Result: {results['success']}/{results['total']} success")
                        
                        total_success += results['success']
                        total_failed += len(results['failed'])
                        
                    except Exception as e:
                        print(f"  ✗ Failed to process post: {e}")
                        continue
                    
                    time.sleep(0.5)  # Avoid too many requests
                
            except Exception as e:
                print(f"✗ Failed to process page: {e}")
                continue
        
        # Display summary
        print(f"\n{'='*60}")
        print(f"All downloads complete!")
        print(f"Total success: {total_success} files")
        print(f"Total failed: {total_failed} files")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


def download_specific_page(session: KemonoSession, profile_url: str, offset: int):
    """
    Download a specific page
    
    Args:
        session: KemonoSession instance
        profile_url: Profile URL
        offset: Page offset
    """
    print(f"\n{'='*60}")
    print(f"Download Specific Page (offset: {offset})")
    print(f"{'='*60}")
    
    try:
        # Parse URL
        service, user_id = parse_profile_url(profile_url)
        
        # Get profile information
        print("\nFetching profile information...")
        profile = fetch_user_profile(session, service, user_id)
        artist_name = profile['name']
        total_posts = profile['post_count']
        
        print(f"Artist: {artist_name}")
        print(f"Total posts: {total_posts}")
        
        if offset >= total_posts:
            print(f"✗ Error: offset {offset} out of range (total {total_posts} posts)")
            return
        
        artist_dir = get_artist_dir(artist_name, service, user_id)
        
        # Get specific page
        print(f"\nFetching posts at offset {offset}...")
        posts = fetch_posts_page(session, service, user_id, offset)
        
        if not posts:
            print("This page has no posts")
            return
        
        print(f"Found {len(posts)} posts")
        
        total_success = 0
        total_failed = 0
        
        for idx, post_summary in enumerate(posts, 1):
            post_id = post_summary['id']
            print(f"\n[{idx}/{len(posts)}] Processing post: {post_id}")
            
            try:
                post_data = fetch_post(session, service, user_id, post_id)
                
                # Format post folder name
                post_folder_name = format_post_folder_name(post_data)
                post_dir = os.path.join('kemono', artist_dir, 'posts', post_folder_name)
                
                results = download_post_files(session, post_data, post_dir)
                print(f"  Result: {results['success']}/{results['total']} success")
                
                total_success += results['success']
                total_failed += len(results['failed'])
                
            except Exception as e:
                print(f"  ✗ Failed to process post: {e}")
                continue
            
            time.sleep(0.5)
        
        # Display summary
        print(f"\n{'='*60}")
        print(f"Page download complete!")
        print(f"Success: {total_success} files")
        print(f"Failed: {total_failed} files")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


def download_page_range(session: KemonoSession, profile_url: str, range_str: str):
    """
    Download a page range
    
    Args:
        session: KemonoSession instance
        profile_url: Profile URL
        range_str: Range string (e.g., "0-150", "start-200", "50-end")
    """
    print(f"\n{'='*60}")
    print(f"Download Page Range: {range_str}")
    print(f"{'='*60}")
    
    try:
        # Parse URL
        service, user_id = parse_profile_url(profile_url)
        
        # Get profile information
        print("\nFetching profile information...")
        profile = fetch_user_profile(session, service, user_id)
        total_posts = profile['post_count']
        artist_name = profile['name']
        
        print(f"Artist: {artist_name}")
        print(f"Total posts: {total_posts}")
        
        # Parse range
        if '-' not in range_str:
            raise ValueError("Invalid range format, should be: start-end, 0-150, start-200, 50-end")
        
        start_str, end_str = range_str.split('-', 1)
        
        start_offset = 0 if start_str.strip().lower() == 'start' else int(start_str.strip())
        end_offset = total_posts if end_str.strip().lower() == 'end' else int(end_str.strip())
        
        # Validate range
        if start_offset < 0 or end_offset < 0:
            raise ValueError("Offset cannot be negative")
        if start_offset >= end_offset:
            raise ValueError("Start offset must be less than end offset")
        if start_offset >= total_posts:
            raise ValueError(f"Start offset {start_offset} out of range (total {total_posts} posts)")
        
        # Adjust end_offset to not exceed total
        end_offset = min(end_offset, total_posts)
        
        print(f"Download range: {start_offset} - {end_offset}")
        
        artist_dir = get_artist_dir(artist_name, service, user_id)
        
        total_success = 0
        total_failed = 0
        
        # Iterate through pages in range
        current_offset = start_offset
        page_num = 1
        
        while current_offset < end_offset:
            print(f"\n{'─'*60}")
            print(f"Processing offset: {current_offset} (page {page_num})")
            print(f"{'─'*60}")
            
            try:
                posts = fetch_posts_page(session, service, user_id, current_offset)
                print(f"Retrieved {len(posts)} posts")
                
                for idx, post_summary in enumerate(posts, 1):
                    post_id = post_summary['id']
                    print(f"\n[{idx}/{len(posts)}] Processing post: {post_id}")
                    
                    try:
                        post_data = fetch_post(session, service, user_id, post_id)
                        
                        # Format post folder name
                        post_folder_name = format_post_folder_name(post_data)
                        post_dir = os.path.join('kemono', artist_dir, 'posts', post_folder_name)
                        
                        results = download_post_files(session, post_data, post_dir)
                        print(f"  Result: {results['success']}/{results['total']} success")
                        
                        total_success += results['success']
                        total_failed += len(results['failed'])
                        
                    except Exception as e:
                        print(f"  ✗ Failed to process post: {e}")
                        continue
                    
                    time.sleep(0.5)
                
            except Exception as e:
                print(f"✗ Failed to process page: {e}")
            
            current_offset += POSTS_PER_PAGE
            page_num += 1
        
        # Display summary
        print(f"\n{'='*60}")
        print(f"Range download complete!")
        print(f"Success: {total_success} files")
        print(f"Failed: {total_failed} files")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


# ============================================================================
# CLI User Interface
# ============================================================================

def print_menu():
    """Display main menu"""
    print("\n" + "="*60)
    print(" "*20 + "Kemono Downloader")
    print("="*60)
    print("1. Download Single Post (enter Post URL)")
    print("2. Download All Posts from Profile (enter Profile URL)")
    print("3. Download Specific Page (enter Profile URL + offset)")
    print("4. Download Page Range (enter Profile URL + range)")
    print("5. Exit")
    print("="*60)


def main():
    """Main function"""
    # Set UTF-8 encoding
    if sys.platform.startswith('win'):
        try:
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
        except:
            pass
    
    print("\n" + "="*60)
    print(" "*15 + "Kemono Downloader Starting...")
    print("="*60)
    print("\nInitializing session...")
    
    try:
        session = KemonoSession()
        print("✓ Session initialization complete\n")
    except Exception as e:
        print(f"✗ Session initialization failed: {e}")
        print("Program will exit")
        return
    
    while True:
        try:
            print_menu()
            choice = input("\nSelect operation (1-5): ").strip()
            
            if choice == '1':
                # Download single post
                url = input("\nEnter Post URL: ").strip()
                if not url:
                    print("✗ URL cannot be empty")
                    continue
                
                try:
                    download_single_post(session, url)
                except Exception as e:
                    print(f"\n✗ Operation failed: {e}")
            
            elif choice == '2':
                # Download all posts
                url = input("\nEnter Profile URL: ").strip()
                if not url:
                    print("✗ URL cannot be empty")
                    continue
                
                confirm = input(f"\nThis will download all posts from this profile. Confirm? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("Cancelled")
                    continue
                
                try:
                    download_all_posts(session, url)
                except Exception as e:
                    print(f"\n✗ Operation failed: {e}")
            
            elif choice == '3':
                # Download specific page
                url = input("\nEnter Profile URL: ").strip()
                if not url:
                    print("✗ URL cannot be empty")
                    continue
                
                offset_str = input("Enter page offset (0, 50, 100, ...): ").strip()
                try:
                    offset = int(offset_str)
                    if offset < 0:
                        print("✗ Offset cannot be negative")
                        continue
                    
                    download_specific_page(session, url, offset)
                except ValueError:
                    print("✗ Offset must be a number")
                except Exception as e:
                    print(f"\n✗ Operation failed: {e}")
            
            elif choice == '4':
                # Download page range
                url = input("\nEnter Profile URL: ").strip()
                if not url:
                    print("✗ URL cannot be empty")
                    continue
                
                range_str = input("Enter range (e.g., 0-150, start-200, 50-end): ").strip()
                if not range_str:
                    print("✗ Range cannot be empty")
                    continue
                
                try:
                    download_page_range(session, url, range_str)
                except Exception as e:
                    print(f"\n✗ Operation failed: {e}")
            
            elif choice == '5':
                # Exit
                print("\nThank you for using Kemono Downloader!")
                print("Goodbye!\n")
                break
            
            else:
                print("\n✗ Invalid choice, please enter 1-5")
            
            # Wait for user confirmation
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n\nInterrupt signal detected")
            confirm = input("Confirm exit? (y/n): ").strip().lower()
            if confirm == 'y':
                print("\nGoodbye!\n")
                break
        except Exception as e:
            print(f"\n✗ Unexpected error occurred: {e}")
            input("\nPress Enter to continue...")


if __name__ == '__main__':
    main()

