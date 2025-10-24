#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download Orchestration Functions
"""

import os
import time
from typing import Dict, Tuple

from api import fetch_post, fetch_posts_page, fetch_user_profile
from config import DEFAULT_DOWNLOAD_DIR, POSTS_PER_PAGE
from download import download_post_files, retry_failed_downloads
from filter import should_download_post
from utils import (
    SEPARATOR,
    SUB_SEPARATOR,
    create_download_result,
    format_artist_folder_name,
    format_post_folder_name,
    parse_post_url,
    parse_profile_url,
    print_separator,
)


# ============================================================================
# Helper Functions
# ============================================================================

def _get_artist_directory(profile: Dict, service: str, user_id: str) -> str:
    """Get artist directory path from profile"""
    return format_artist_folder_name(
        profile['name'],
        service,
        user_id,
        indexed=profile.get('indexed', ''),
        updated=profile.get('updated', ''),
        public_id=profile.get('public_id', '')
    )


def _process_single_post(session, service: str, user_id: str, post_id: str,
                         artist_dir: str, download_dir: str) -> Dict:
    """Process and download a single post"""
    post_data = fetch_post(session, service, user_id, post_id)
    
    if not should_download_post(post_data):
        post_title = post_data.get('post', {}).get('title', post_id)
        print(f"  ⊘ Skipped by filter: {post_title}")
        return create_download_result()
    
    post_folder_name = format_post_folder_name(post_data)
    post_dir = os.path.join(download_dir, artist_dir, post_folder_name)
    results = download_post_files(session, post_data, post_dir)
    print(f"  Result: {results['success']}/{results['total']} success")
    
    return results


def _print_summary(title: str, success: int, failed: int):
    """Print download summary"""
    print_separator(title)
    print(f"Success: {success} files")
    print(f"Failed: {failed} files")
    print(SEPARATOR)


def _parse_range(range_str: str, total_posts: int) -> Tuple[int, int]:
    """Parse and validate range string"""
    if '-' not in range_str:
        raise ValueError("Invalid range format, should be: start-end, 0-150, start-200, 50-end")
    
    start_str, end_str = range_str.split('-', 1)
    start = 0 if start_str.strip().lower() == 'start' else int(start_str.strip())
    end = total_posts if end_str.strip().lower() == 'end' else int(end_str.strip())
    
    if start < 0 or end < 0:
        raise ValueError("Offset cannot be negative")
    if start >= end:
        raise ValueError("Start offset must be less than end offset")
    if start >= total_posts:
        raise ValueError(f"Start offset {start} out of range (total {total_posts} posts)")
    
    return start, min(end, total_posts)


# ============================================================================
# Single Post Download
# ============================================================================

def download_single_post(session, post_url: str, download_dir: str = None):
    """Download a single post"""
    download_dir = download_dir or DEFAULT_DOWNLOAD_DIR
    
    print(f"\n{SEPARATOR}")
    print("Download Single Post")
    print(SEPARATOR)
    print(f"URL: {post_url}")
    print(f"Download directory: {download_dir}")
    
    try:
        service, user_id, post_id = parse_post_url(post_url)
        print(f"Service: {service}, User ID: {user_id}, Post ID: {post_id}")
        
        print("\nFetching user information...")
        profile = fetch_user_profile(session, service, user_id)
        print(f"Artist: {profile['name']}")
        
        print("\nFetching post data...")
        post_data = fetch_post(session, service, user_id, post_id)
        print(f"Post title: {post_data.get('post', {}).get('title', post_id)}")
        
        artist_dir = _get_artist_directory(profile, service, user_id)
        post_folder_name = format_post_folder_name(post_data)
        post_dir = os.path.join(download_dir, artist_dir, post_folder_name)
        
        print(f"\nDownloading files to: {post_dir}")
        results = download_post_files(session, post_data, post_dir)
        
        _print_summary("Download complete!", results['success'], len(results['failed']))
        if results['failed']:
            for item in results['failed']:
                print(f"  - {item['url']}")
        
        return results
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


# ============================================================================
# Batch Download Workflows
# ============================================================================

def download_all_posts(session, profile_url: str, download_dir: str = None):
    """Download all posts from a profile"""
    download_dir = download_dir or DEFAULT_DOWNLOAD_DIR
    
    print(f"\n{SEPARATOR}")
    print("Download All Posts")
    print(f"{SEPARATOR}\nDownload directory: {download_dir}")
    
    try:
        service, user_id = parse_profile_url(profile_url)
        
        print("\nFetching profile information...")
        profile = fetch_user_profile(session, service, user_id)
        print(f"Artist: {profile['name']}")
        print(f"Total posts: {profile['post_count']}")
        
        if profile['post_count'] == 0:
            print("This artist has no posts")
            return create_download_result()
        
        total_pages = (profile['post_count'] + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE
        print(f"Total pages: {total_pages}")
        
        artist_dir = _get_artist_directory(profile, service, user_id)
        stats = {'success': 0, 'failed': 0, 'failed_items': []}
        
        for page_num in range(total_pages):
            offset = page_num * POSTS_PER_PAGE
            print(f"\n{SUB_SEPARATOR}")
            print(f"Processing page {page_num + 1}/{total_pages} (offset: {offset})")
            print(SUB_SEPARATOR)
            
            try:
                posts = fetch_posts_page(session, service, user_id, offset)
                print(f"Retrieved {len(posts)} posts")
                
                for idx, post_summary in enumerate(posts, 1):
                    print(f"\n[{idx}/{len(posts)}] Processing post: {post_summary['id']}")
                    
                    try:
                        results = _process_single_post(
                            session, service, user_id, post_summary['id'],
                            artist_dir, download_dir
                        )
                        stats['success'] += results['success']
                        stats['failed'] += len(results['failed'])
                        stats['failed_items'].extend(results['failed'])
                        
                    except Exception as e:
                        print(f"  ✗ Failed to process post: {e}")
                    
                    time.sleep(0.5)
                
            except Exception as e:
                print(f"✗ Failed to process page: {e}")
        
        _print_summary("All downloads complete!", stats['success'], stats['failed'])
        return {'total': stats['success'] + stats['failed'],
                'success': stats['success'],
                'failed': stats['failed_items']}
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


def download_specific_page(session, profile_url: str, offset: int, download_dir: str = None):
    """Download a specific page"""
    download_dir = download_dir or DEFAULT_DOWNLOAD_DIR
    
    print(f"\n{SEPARATOR}")
    print(f"Download Specific Page (offset: {offset})")
    print(f"{SEPARATOR}\nDownload directory: {download_dir}")
    
    try:
        service, user_id = parse_profile_url(profile_url)
        
        print("\nFetching profile information...")
        profile = fetch_user_profile(session, service, user_id)
        print(f"Artist: {profile['name']}")
        print(f"Total posts: {profile['post_count']}")
        
        if offset >= profile['post_count']:
            print(f"✗ Error: offset {offset} out of range (total {profile['post_count']} posts)")
            return create_download_result()
        
        artist_dir = _get_artist_directory(profile, service, user_id)
        
        print(f"\nFetching posts at offset {offset}...")
        posts = fetch_posts_page(session, service, user_id, offset)
        
        if not posts:
            print("This page has no posts")
            return create_download_result()
        
        print(f"Found {len(posts)} posts")
        stats = {'success': 0, 'failed': 0, 'failed_items': []}
        
        for idx, post_summary in enumerate(posts, 1):
            print(f"\n[{idx}/{len(posts)}] Processing post: {post_summary['id']}")
            
            try:
                results = _process_single_post(
                    session, service, user_id, post_summary['id'],
                    artist_dir, download_dir
                )
                stats['success'] += results['success']
                stats['failed'] += len(results['failed'])
                stats['failed_items'].extend(results['failed'])
                
            except Exception as e:
                print(f"  ✗ Failed to process post: {e}")
            
            time.sleep(0.5)
        
        _print_summary("Page download complete!", stats['success'], stats['failed'])
        return {'total': stats['success'] + stats['failed'],
                'success': stats['success'],
                'failed': stats['failed_items']}
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


def download_page_range(session, profile_url: str, range_str: str, download_dir: str = None):
    """Download a page range"""
    download_dir = download_dir or DEFAULT_DOWNLOAD_DIR
    
    print(f"\n{SEPARATOR}")
    print(f"Download Page Range: {range_str}")
    print(f"{SEPARATOR}\nDownload directory: {download_dir}")
    
    try:
        service, user_id = parse_profile_url(profile_url)
        
        print("\nFetching profile information...")
        profile = fetch_user_profile(session, service, user_id)
        print(f"Artist: {profile['name']}")
        print(f"Total posts: {profile['post_count']}")
        
        start_offset, end_offset = _parse_range(range_str, profile['post_count'])
        print(f"Download range: {start_offset} - {end_offset}")
        
        artist_dir = _get_artist_directory(profile, service, user_id)
        stats = {'success': 0, 'failed': 0, 'failed_items': []}
        current_offset = start_offset
        
        while current_offset < end_offset:
            print(f"\n{SUB_SEPARATOR}")
            print(f"Processing offset {current_offset}")
            print(SUB_SEPARATOR)
            
            try:
                posts = fetch_posts_page(session, service, user_id, current_offset)
                print(f"Retrieved {len(posts)} posts")
                
                for idx, post_summary in enumerate(posts, 1):
                    if current_offset + idx - 1 >= end_offset:
                        break
                    
                    print(f"\n[{idx}/{len(posts)}] Processing post: {post_summary['id']}")
                    
                    try:
                        results = _process_single_post(
                            session, service, user_id, post_summary['id'],
                            artist_dir, download_dir
                        )
                        stats['success'] += results['success']
                        stats['failed'] += len(results['failed'])
                        stats['failed_items'].extend(results['failed'])
                        
                    except Exception as e:
                        print(f"  ✗ Failed to process post: {e}")
                    
                    time.sleep(0.5)
                
            except Exception as e:
                print(f"✗ Failed to process page: {e}")
            
            current_offset += POSTS_PER_PAGE
        
        _print_summary("Range download complete!", stats['success'], stats['failed'])
        return {'total': stats['success'] + stats['failed'],
                'success': stats['success'],
                'failed': stats['failed_items']}
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


def download_multiple_posts(session, urls: list, download_dir: str = None):
    """Download multiple post URLs"""
    download_dir = download_dir or DEFAULT_DOWNLOAD_DIR
    
    print(f"\n{SEPARATOR}")
    print(f"Download Multiple Posts")
    print(SEPARATOR)
    print(f"Total URLs: {len(urls)}")
    print(f"Download directory: {download_dir}")
    
    stats = {'success': 0, 'failed': 0, 'failed_items': []}
    processed_posts = set()
    
    for idx, url in enumerate(urls, 1):
        print(f"\n{SUB_SEPARATOR}")
        print(f"[{idx}/{len(urls)}] Processing URL: {url}")
        print(SUB_SEPARATOR)
        
        try:
            service, user_id, post_id = parse_post_url(url)
            
            # Skip duplicate posts
            post_key = f"{service}_{user_id}_{post_id}"
            if post_key in processed_posts:
                print("  ⊘ Skipped: duplicate URL")
                continue
            processed_posts.add(post_key)
            
            print(f"Service: {service}, User ID: {user_id}, Post ID: {post_id}")
            
            # Fetch user profile
            profile = fetch_user_profile(session, service, user_id)
            print(f"Artist: {profile['name']}")
            
            # Fetch and process post
            post_data = fetch_post(session, service, user_id, post_id)
            post_title = post_data.get('post', {}).get('title', post_id)
            print(f"Post title: {post_title}")
            
            if not should_download_post(post_data):
                print(f"  ⊘ Skipped by filter: {post_title}")
                continue
            
            artist_dir = _get_artist_directory(profile, service, user_id)
            post_folder_name = format_post_folder_name(post_data)
            post_dir = os.path.join(download_dir, artist_dir, post_folder_name)
            
            print(f"Downloading to: {post_dir}")
            results = download_post_files(session, post_data, post_dir)
            
            stats['success'] += results['success']
            stats['failed'] += len(results['failed'])
            stats['failed_items'].extend(results['failed'])
            
            print(f"Result: {results['success']}/{results['total']} success")
            
        except ValueError as e:
            print(f"  ✗ Invalid URL: {e}")
        except Exception as e:
            print(f"  ✗ Failed to process URL: {e}")
        
        time.sleep(0.5)
    
    _print_summary("Batch download complete!", stats['success'], stats['failed'])
    return {'total': stats['success'] + stats['failed'],
            'success': stats['success'],
            'failed': stats['failed_items']}
