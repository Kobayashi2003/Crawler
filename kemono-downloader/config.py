#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration and Constants
"""

# ============================================================================
# Domain Configuration
# ============================================================================

KEMONO_DOMAIN = "kemono.cr"
BASE_API_URL = f"https://{KEMONO_DOMAIN}/api/v1"
BASE_SERVER = f"https://{KEMONO_DOMAIN}"

# ============================================================================
# HTTP Configuration
# ============================================================================

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

# ============================================================================
# Download Configuration
# ============================================================================

POSTS_PER_PAGE = 50
MAX_RETRIES = 10
RETRY_DELAY_BASE = 5  # seconds, for exponential backoff

# Default download directory
DEFAULT_DOWNLOAD_DIR = "kemono"

# ============================================================================
# Naming Configuration
# ============================================================================

# Date format for time variables (uses Python strftime format)
# Applies to: {published}, {indexed}, {updated}
DATE_FORMAT = "%Y-%m-%d"

# Artist folder naming configuration
# Available variables: {id}, {name}, {service}, {indexed}, {updated}, {public_id}
ARTIST_FOLDER_NAME_FORMAT = "{name}"

# Post folder naming configuration
# Available variables: {id}, {title}, {published}
POST_FOLDER_NAME_FORMAT = "{published}-{title}"

# File naming configuration
# Available variables: {idx}, {name}
FILE_NAME_FORMAT = "{idx}"
