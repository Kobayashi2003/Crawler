#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post Filter Module

Users can customize filtering rules by modifying the should_download_post() function
"""

from typing import Dict


# ============================================================================
# Example Filter Functions
# ============================================================================

def contains_keyword(post_data: Dict, keyword: str) -> bool:
    """
    Check if post title contains specified keyword
    
    Args:
        post_data: Post data dictionary
        keyword: Keyword to search for
        
    Returns:
        True if title contains keyword
    """
    title = post_data.get('post', {}).get('title', '').lower()
    return keyword.lower() in title


def not_contains_keyword(post_data: Dict, keyword: str) -> bool:
    """
    Check if post title does not contain specified keyword
    
    Args:
        post_data: Post data dictionary
        keyword: Keyword to search for
        
    Returns:
        True if title does not contain keyword
    """
    return not contains_keyword(post_data, keyword)


def contains_any_keywords(post_data: Dict, keywords: list) -> bool:
    """
    Check if post title contains any of the specified keywords
    
    Args:
        post_data: Post data dictionary
        keywords: List of keywords
        
    Returns:
        True if title contains any keyword
    """
    title = post_data.get('post', {}).get('title', '').lower()
    return any(keyword.lower() in title for keyword in keywords)


def contains_all_keywords(post_data: Dict, keywords: list) -> bool:
    """
    Check if post title contains all specified keywords
    
    Args:
        post_data: Post data dictionary
        keywords: List of keywords
        
    Returns:
        True if title contains all keywords
    """
    title = post_data.get('post', {}).get('title', '').lower()
    return all(keyword.lower() in title for keyword in keywords)


def has_attachments(post_data: Dict) -> bool:
    """
    Check if post has attachments
    
    Args:
        post_data: Post data dictionary
        
    Returns:
        True if post has attachments
    """
    return len(post_data.get('attachments', [])) > 0


def has_videos(post_data: Dict) -> bool:
    """
    Check if post has videos
    
    Args:
        post_data: Post data dictionary
        
    Returns:
        True if post has videos
    """
    return len(post_data.get('videos', [])) > 0


def has_images(post_data: Dict) -> bool:
    """
    Check if post has images
    
    Args:
        post_data: Post data dictionary
        
    Returns:
        True if post has images
    """
    return len(post_data.get('previews', [])) > 0


def has_any_files(post_data: Dict) -> bool:
    """
    Check if post has any files (attachments, videos, or images)
    
    Args:
        post_data: Post data dictionary
        
    Returns:
        True if post has any files
    """
    return (has_attachments(post_data) or 
            has_videos(post_data) or 
            has_images(post_data))


def published_after(post_data: Dict, date_str: str) -> bool:
    """
    Check if post was published after specified date
    
    Args:
        post_data: Post data dictionary
        date_str: Date string in format "YYYY-MM-DD"
        
    Returns:
        True if post published after date
    """
    try:
        published = post_data.get('post', {}).get('published', '')
        if not published:
            return False
        post_date = published.split('T')[0]  # Get YYYY-MM-DD part
        return post_date > date_str
    except:
        return False


def published_before(post_data: Dict, date_str: str) -> bool:
    """
    Check if post was published before specified date
    
    Args:
        post_data: Post data dictionary
        date_str: Date string in format "YYYY-MM-DD"
        
    Returns:
        True if post published before date
    """
    try:
        published = post_data.get('post', {}).get('published', '')
        if not published:
            return False
        post_date = published.split('T')[0]  # Get YYYY-MM-DD part
        return post_date < date_str
    except:
        return False


# ============================================================================
# Main Filter Function
# ============================================================================

def should_download_post(post_data: Dict) -> bool:
    """
    Main filter function - Determines whether to download a post
    
    Default behavior: Download all posts (return True)
    
    Users can modify this function to customize filtering rules
    
    Args:
        post_data: Post data dictionary containing 'post' key and other information
        
    Returns:
        True = Download this post
        False = Skip this post
        
    Example usage:
    
    # Example 1: Only download posts with "illustration" in title
    return contains_keyword(post_data, "illustration")
    
    # Example 2: Skip posts with "sketch" in title
    return not_contains_keyword(post_data, "sketch")
    
    # Example 3: Only download posts containing "artwork" or "illustration"
    return contains_any_keywords(post_data, ["artwork", "illustration"])
    
    # Example 4: Only download posts containing both "high" and "resolution"
    return contains_all_keywords(post_data, ["high", "resolution"])
    
    # Example 5: Only download posts with attachments
    return has_attachments(post_data)
    
    # Example 6: Only download posts with videos
    return has_videos(post_data)
    
    # Example 7: Only download posts with any files
    return has_any_files(post_data)
    
    # Example 8: Only download posts published after 2024
    return published_after(post_data, "2024-01-01")
    
    # Example 9: Combined conditions - Posts after 2024 with "artwork"
    return (published_after(post_data, "2024-01-01") and 
            contains_keyword(post_data, "artwork"))
    
    # Example 10: Complex conditions - Posts with files but not "WIP"
    return has_any_files(post_data) and not_contains_keyword(post_data, "WIP")
    """

    # Default: Download all posts
    return True
    
    # ========== Add your custom rules below ==========
    
    # Uncomment and modify examples below to enable filtering:
    
    # Example: Only download posts with "artwork" in title
    # return contains_keyword(post_data, "artwork")
    
    # Example: Skip posts with "sketch" or "WIP" in title
    # return not contains_any_keywords(post_data, ["sketch", "WIP"])
    
    # Example: Only download posts after 2024 with files
    # return published_after(post_data, "2024-01-01") and has_any_files(post_data)
