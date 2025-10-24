#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session Management for Kemono
"""

import requests


BASE_SERVER = "https://kemono.cr"

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
