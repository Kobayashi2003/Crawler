#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session Management
"""

import requests

from config import BASE_SERVER, HEADERS, INIT_HEADERS


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
