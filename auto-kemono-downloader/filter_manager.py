#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post Filter Management
"""

from typing import Dict, Optional


class FilterManager:
    """Manage post filtering logic"""
    
    def __init__(self, global_filter: Optional[Dict] = None):
        """Initialize filter manager"""
        self.global_filter = global_filter or {}
    
    def should_download(self, post_data: Dict, artist_filter: Optional[Dict] = None,
                       use_global: bool = True) -> bool:
        """Determine if a post should be downloaded"""
        # Apply global filter if enabled
        if use_global and self.global_filter:
            if not self._apply_filter(post_data, self.global_filter):
                return False
        
        # Apply artist-specific filter
        if artist_filter:
            if not self._apply_filter(post_data, artist_filter):
                return False
        
        return True
    
    def _apply_filter(self, post_data: Dict, filter_config: Dict) -> bool:
        """Apply a single filter configuration"""
        # Check keywords
        keywords = filter_config.get('keywords', [])
        if keywords and not self._check_keywords(post_data, keywords):
            return False
        
        # Check exclude keywords
        exclude_keywords = filter_config.get('exclude_keywords', [])
        if exclude_keywords and self._check_exclude_keywords(post_data, exclude_keywords):
            return False
        
        # Check date range
        date_after = filter_config.get('date_after')
        date_before = filter_config.get('date_before')
        if not self._check_date_range(post_data, date_after, date_before):
            return False
        
        # Check file requirements
        if filter_config.get('require_files') and not self._has_any_files(post_data):
            return False
        
        if filter_config.get('require_images') and not self._has_images(post_data):
            return False
        
        if filter_config.get('require_videos') and not self._has_videos(post_data):
            return False
        
        if filter_config.get('require_attachments') and not self._has_attachments(post_data):
            return False
        
        return True
    
    def _check_keywords(self, post_data: Dict, keywords: list) -> bool:
        """Check if post title contains any of the keywords"""
        title = post_data.get('post', {}).get('title', '').lower()
        return any(keyword.lower() in title for keyword in keywords)
    
    def _check_exclude_keywords(self, post_data: Dict, keywords: list) -> bool:
        """Check if post title contains any excluded keywords"""
        title = post_data.get('post', {}).get('title', '').lower()
        return any(keyword.lower() in title for keyword in keywords)
    
    def _check_date_range(self, post_data: Dict, date_after: Optional[str], 
                         date_before: Optional[str]) -> bool:
        """Check if post date is within range"""
        try:
            published = post_data.get('post', {}).get('published', '')
            if not published:
                return True
            
            post_date = published.split('T')[0]  # Get YYYY-MM-DD part
            
            if date_after and post_date <= date_after:
                return False
            
            if date_before and post_date >= date_before:
                return False
            
            return True
        except:
            return True
    
    def _has_attachments(self, post_data: Dict) -> bool:
        """Check if post has attachments"""
        return len(post_data.get('attachments', [])) > 0
    
    def _has_videos(self, post_data: Dict) -> bool:
        """Check if post has videos"""
        return len(post_data.get('videos', [])) > 0
    
    def _has_images(self, post_data: Dict) -> bool:
        """Check if post has images"""
        return len(post_data.get('previews', [])) > 0
    
    def _has_any_files(self, post_data: Dict) -> bool:
        """Check if post has any files"""
        return (self._has_attachments(post_data) or 
                self._has_videos(post_data) or 
                self._has_images(post_data))
