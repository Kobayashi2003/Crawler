#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Functions
"""

import time
from typing import Dict, List

from config import BASE_API_URL, MAX_RETRIES, RETRY_DELAY_BASE
from utils import retry_on_error


@retry_on_error(max_retries=MAX_RETRIES, base_delay=2, exponential_backoff=False)
def fetch_user_profile(session, service: str, user_id: str) -> Dict:
    """Fetch user profile information"""
    url = f"{BASE_API_URL}/{service}/user/{user_id}/profile"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


@retry_on_error(max_retries=MAX_RETRIES, base_delay=RETRY_DELAY_BASE, exponential_backoff=True)
def fetch_post(session, service: str, user_id: str, post_id: str) -> Dict:
    """Fetch detailed post information"""
    url = f"{BASE_API_URL}/{service}/user/{user_id}/post/{post_id}"
    time.sleep(1)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


@retry_on_error(max_retries=MAX_RETRIES, base_delay=2, exponential_backoff=False)
def fetch_posts_page(session, service: str, user_id: str, offset: int = 0) -> List[Dict]:
    """Fetch posts list for a specific page"""
    url = f"{BASE_API_URL}/{service}/user/{user_id}/posts"
    if offset > 0:
        url += f"?o={offset}"
    
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()
