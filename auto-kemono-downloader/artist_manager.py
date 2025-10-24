#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Artist Management
"""

import json
import os
import uuid
from typing import Dict, List, Optional


class ArtistManager:
    """Manage artist configurations"""
    
    def __init__(self, artists_file: str = "artists.json"):
        """Initialize artist manager"""
        self.artists_file = artists_file
        self.artists = []
        self.load()
    
    def add_artist(self, name: str, service: str, user_id: str, 
                   alias: Optional[str] = None,
                   last_post_date: Optional[str] = None, 
                   timer: Optional[Dict] = None,
                   config: Optional[Dict] = None, 
                   filter_config: Optional[Dict] = None) -> str:
        """Add a new artist"""
        # Generate unique ID
        artist_id = str(uuid.uuid4())
        
        # Build artist URL
        url = f"https://kemono.cr/{service}/user/{user_id}"
        
        # Create artist data
        artist_data = {
            "id": artist_id,
            "name": name,
            "alias": alias or "",
            "service": service,
            "user_id": user_id,
            "url": url,
            "last_post_date": last_post_date,
            "timer": timer,
            "use_global_filter": True,
            "config_override": config or {},
            "filter": filter_config or {}
        }
        
        self.artists.append(artist_data)
        self.save()
        
        display_name = alias if alias else name
        print(f"✓ Added artist: {display_name} ({service}/{user_id})")
        return artist_id
    
    def remove_artist(self, artist_id: str) -> bool:
        """Remove an artist by ID"""
        for i, artist in enumerate(self.artists):
            if artist['id'] == artist_id:
                removed = self.artists.pop(i)
                self.save()
                print(f"✓ Removed artist: {removed['name']}")
                return True
        
        print(f"✗ Artist not found: {artist_id}")
        return False
    
    def update_artist(self, artist_id: str, **kwargs) -> bool:
        """Update artist data"""
        for artist in self.artists:
            if artist['id'] == artist_id:
                artist.update(kwargs)
                self.save()
                print(f"✓ Updated artist: {artist['name']}")
                return True
        
        print(f"✗ Artist not found: {artist_id}")
        return False
    
    def get_artist(self, artist_id: str) -> Optional[Dict]:
        """Get artist by ID"""
        for artist in self.artists:
            if artist['id'] == artist_id:
                return artist.copy()
        return None
    
    def get_all_artists(self) -> List[Dict]:
        """Get all artists"""
        return [artist.copy() for artist in self.artists]
    
    def update_last_post_date(self, artist_id: str, date: str) -> None:
        """Update the last fetched post date for an artist"""
        for artist in self.artists:
            if artist['id'] == artist_id:
                artist['last_post_date'] = date
                self.save()
                break
    
    def save(self) -> None:
        """Save artists to file"""
        try:
            data = {"artists": self.artists}
            with open(self.artists_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving artists: {e}")
    
    def load(self) -> None:
        """Load artists from file"""
        if not os.path.exists(self.artists_file):
            print(f"Artists file not found, creating: {self.artists_file}")
            self.save()
            return
        
        try:
            with open(self.artists_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.artists = data.get('artists', [])
            print(f"Loaded {len(self.artists)} artists from {self.artists_file}")
        except Exception as e:
            print(f"Error loading artists: {e}")
            self.artists = []
