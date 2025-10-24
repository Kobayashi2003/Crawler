#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Management
"""

import json
import os
from typing import Dict


DEFAULT_CONFIG = {
    "download_dir": "I:/kemono",
    "date_format": "%Y.%m.%d",
    "artist_folder_format": "{name}",
    "post_folder_format": "[{published}] {title}",
    "file_name_format": "{idx}",
    "rename_images_only": True,
    "image_extensions": [".jpe", ".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "char_replacement": {
        "/": "／",
        "\\": "＼",
        ":": "：",
        "*": "＊",
        "?": "？",
        '"': "＂",
        "<": "＜",
        ">": "＞",
        "|": "｜"
    },
    "save_content_to_file": True,
    "global_timer": {
        "type": "daily",
        "time": "02:00"
    }
}


class ConfigManager:
    """Manage global and per-artist configurations"""
    
    def __init__(self, config_file: str = "config.json"):
        """Initialize configuration manager"""
        self.config_file = config_file
        self.config = DEFAULT_CONFIG.copy()
        self.load()
    
    def get_global_config(self) -> Dict:
        """Get global configuration"""
        return self.config.copy()
    
    def update_global_config(self, **kwargs) -> None:
        """Update global configuration"""
        self.config.update(kwargs)
        self.save()
    
    def get_artist_config(self, artist_data: Dict) -> Dict:
        """Get merged configuration for an artist"""
        config = self.config.copy()
        
        # Override with artist-specific config if present
        artist_override = artist_data.get('config_override', {})
        if artist_override:
            config.update(artist_override)
        
        return config
    
    def validate_config(self, config: Dict) -> bool:
        """Validate configuration structure"""
        required_keys = ['download_dir', 'date_format', 'artist_folder_format', 
                        'post_folder_format', 'file_name_format']
        
        for key in required_keys:
            if key not in config:
                return False
        
        # Validate timer if present
        if 'global_timer' in config:
            timer = config['global_timer']
            if not isinstance(timer, dict):
                return False
            if 'type' not in timer or timer['type'] not in ['daily', 'weekly', 'monthly']:
                return False
            if 'time' not in timer:
                return False
        
        return True
    
    def save(self) -> None:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    def load(self) -> None:
        """Load configuration from file"""
        if not os.path.exists(self.config_file):
            print(f"Config file not found, creating default: {self.config_file}")
            self.save()
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            if self.validate_config(loaded_config):
                self.config = loaded_config
                print(f"Configuration loaded from {self.config_file}")
            else:
                print(f"Invalid configuration, using defaults")
                self.save()
        except Exception as e:
            print(f"Error loading configuration: {e}, using defaults")
            self.save()
