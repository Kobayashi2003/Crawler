#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download Orchestration
"""

import os
from typing import Dict, List

from api import fetch_post, fetch_posts_page
from config_manager import ConfigManager
from download import download_post_files
from filter_manager import FilterManager
from logger import DownloadLogger
from utils import format_artist_folder_name, format_post_folder_name


class DownloadManager:
    """Manage download operations"""
    
    def __init__(self, session, config_manager: ConfigManager, 
                 filter_manager: FilterManager):
        """Initialize download manager"""
        self.session = session
        self.config_manager = config_manager
        self.filter_manager = filter_manager
        self.logger = DownloadLogger()
    
    def download_artist_updates(self, artist_data: Dict) -> Dict:
        """Download new posts for an artist"""
        display_name = artist_data.get('alias') if artist_data.get('alias') else artist_data['name']
        print(f"\n{'='*60}")
        print(f"Checking artist: {display_name}")
        print(f"{'='*60}")
        
        # Log artist check
        self.logger.log_artist_check(display_name, artist_data['id'])
        
        # Get artist configuration
        config = self.config_manager.get_artist_config(artist_data)
        
        # Fetch new posts
        new_posts = self._fetch_new_posts(artist_data)
        
        display_name = artist_data.get('alias') if artist_data.get('alias') else artist_data['name']
        
        if not new_posts:
            print("No new posts found")
            return {
                'artist_id': artist_data['id'],
                'artist_name': display_name,
                'posts_checked': 0,
                'posts_downloaded': 0,
                'files_downloaded': 0,
                'files_failed': 0,
                'latest_post_date': artist_data.get('last_post_date'),
                'errors': []
            }
        
        print(f"Found {len(new_posts)} new posts")
        self.logger.log_posts_found(display_name, len(new_posts))
        
        # Download posts
        result = self._download_posts(artist_data, new_posts, config)
        
        # Log summary
        self.logger.log_artist_summary(
            display_name,
            result['posts_checked'],
            result['posts_downloaded'],
            result['files_downloaded'],
            result['files_failed']
        )
        
        return result
    
    def _fetch_new_posts(self, artist_data: Dict) -> List[Dict]:
        """Fetch posts newer than last_post_date"""
        service = artist_data['service']
        user_id = artist_data['user_id']
        last_date = artist_data.get('last_post_date')
        
        new_posts = []
        offset = 0
        
        try:
            while True:
                posts = fetch_posts_page(self.session, service, user_id, offset)
                
                if not posts:
                    break
                
                for post in posts:
                    post_date = post.get('published', '')
                    
                    # If we have a last_date, only get posts after it
                    if last_date and post_date <= last_date:
                        return new_posts
                    
                    new_posts.append(post)
                
                # If no last_date, only get first page
                if not last_date:
                    break
                
                offset += 50
        
        except Exception as e:
            print(f"Error fetching posts: {e}")
        
        return new_posts
    
    def _download_posts(self, artist_data: Dict, posts: List[Dict], 
                       config: Dict) -> Dict:
        """Download a list of posts"""
        display_name = artist_data.get('alias') if artist_data.get('alias') else artist_data['name']
        
        result = {
            'artist_id': artist_data['id'],
            'artist_name': display_name,
            'posts_checked': len(posts),
            'posts_downloaded': 0,
            'files_downloaded': 0,
            'files_failed': 0,
            'latest_post_date': artist_data.get('last_post_date'),
            'errors': []
        }
        
        for post in posts:
            try:
                # Fetch full post data
                full_post = fetch_post(self.session, artist_data['service'], 
                                      artist_data['user_id'], post['id'])
                
                # Apply filters
                use_global = artist_data.get('use_global_filter', True)
                artist_filter = artist_data.get('filter', {})
                
                if not self.filter_manager.should_download(full_post, artist_filter, use_global):
                    post_title = post.get('title', 'Untitled')
                    print(f"Skipped (filtered): {post_title}")
                    self.logger.log_post_filtered(post_title)
                    continue
                
                # Log post download start
                post_title = post.get('title', 'Untitled')
                self.logger.log_post_download_start(
                    artist_data.get('alias') or artist_data['name'],
                    post_title,
                    str(post.get('id', 'unknown'))
                )
                
                # Download post
                save_dir = self._build_save_path(artist_data, full_post, config)
                download_result = download_post_files(
                    self.session, full_post, save_dir, config,
                    config.get('save_content_to_file', True),
                    self.logger
                )
                
                # Log post completion
                self.logger.log_post_complete(
                    post_title,
                    download_result['success'],
                    len(download_result['failed'])
                )
                
                result['posts_downloaded'] += 1
                result['files_downloaded'] += download_result['success']
                result['files_failed'] += len(download_result['failed'])
                
                # Update latest post date
                post_date = post.get('published', '')
                if not result['latest_post_date'] or post_date > result['latest_post_date']:
                    result['latest_post_date'] = post_date
                
            except Exception as e:
                error_msg = f"Error downloading post {post.get('id')}: {e}"
                print(f"✗ {error_msg}")
                self.logger.log_error(f"post {post.get('id')}", str(e))
                result['errors'].append(error_msg)
        
        return result
    
    def _build_save_path(self, artist_data: Dict, post_data: Dict, 
                        config: Dict) -> str:
        """Build the save path for a post"""
        # Get base download directory
        base_dir = config.get('download_dir', 'downloads')
        
        # Format artist folder name
        artist_folder = format_artist_folder_name(artist_data, config)
        
        # Format post folder name
        post_folder = format_post_folder_name(post_data, config)
        
        return os.path.join(base_dir, artist_folder, post_folder)
