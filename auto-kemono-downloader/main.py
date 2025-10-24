#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Kemono Downloader - Main Entry Point
"""

import signal
import sys

from artist_manager import ArtistManager
from cli import CLI
from config_manager import ConfigManager
from download_manager import DownloadManager
from filter_manager import FilterManager
from scheduler import Scheduler
from session import KemonoSession


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n\nReceived shutdown signal, cleaning up...")
    sys.exit(0)


def main():
    """Main application entry point"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Initializing Auto Kemono Downloader...")
    
    try:
        # Initialize managers
        config_manager = ConfigManager("config.json")
        artist_manager = ArtistManager("artists.json")
        
        # Get global filter from config
        global_config = config_manager.get_global_config()
        global_filter = global_config.get('global_filter', {})
        filter_manager = FilterManager(global_filter)
        
        # Initialize session
        session = KemonoSession()
        
        # Initialize download manager
        download_manager = DownloadManager(session, config_manager, filter_manager)
        
        # Initialize scheduler
        scheduler = Scheduler(artist_manager, download_manager)
        
        # Initialize CLI
        cli = CLI(artist_manager, config_manager, scheduler)
        
        # Start scheduler
        scheduler.start()
        
        # Start CLI (blocking)
        cli.start()
        
        # Cleanup
        scheduler.stop()
        print("Shutdown complete")
    
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
