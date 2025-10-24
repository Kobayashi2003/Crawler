#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduling System
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Dict

from artist_manager import ArtistManager
from download_manager import DownloadManager


class Scheduler:
    """Handle scheduled artist checks"""
    
    def __init__(self, artist_manager: ArtistManager, 
                 download_manager: DownloadManager):
        """Initialize scheduler"""
        self.artist_manager = artist_manager
        self.download_manager = download_manager
        self.running = False
        self.thread = None
        self.next_run_times = {}
    
    def start(self) -> None:
        """Start the scheduler thread"""
        if self.running:
            print("Scheduler already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("Scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler thread"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("Scheduler stopped")
    
    def _calculate_next_run(self, timer: Dict) -> datetime:
        """Calculate next run time based on timer configuration"""
        now = datetime.now()
        timer_type = timer.get('type', 'daily')
        time_str = timer.get('time', '02:00')
        
        try:
            hour, minute = map(int, time_str.split(':'))
        except:
            hour, minute = 2, 0
        
        if timer_type == 'daily':
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
        
        elif timer_type == 'weekly':
            day = timer.get('day', 0)  # 0 = Monday
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            days_ahead = day - now.weekday()
            if days_ahead <= 0 or (days_ahead == 0 and next_run <= now):
                days_ahead += 7
            next_run += timedelta(days=days_ahead)
        
        elif timer_type == 'monthly':
            day = timer.get('day', 1)  # 1-31
            next_run = now.replace(day=day, hour=hour, minute=minute, 
                                  second=0, microsecond=0)
            if next_run <= now:
                # Move to next month
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
        
        else:
            # Default to daily
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
        
        return next_run
    
    def _check_and_download(self, artist_data: Dict) -> None:
        """Check and download updates for an artist"""
        try:
            result = self.download_manager.download_artist_updates(artist_data)
            
            # Update last post date if we downloaded anything
            if result['latest_post_date']:
                self.artist_manager.update_last_post_date(
                    artist_data['id'], 
                    result['latest_post_date']
                )
            
            # Print summary
            display_name = artist_data.get('alias') if artist_data.get('alias') else artist_data['name']
            print(f"\nSummary for {display_name}:")
            print(f"  Posts checked: {result['posts_checked']}")
            print(f"  Posts downloaded: {result['posts_downloaded']}")
            print(f"  Files downloaded: {result['files_downloaded']}")
            if result['files_failed'] > 0:
                print(f"  Files failed: {result['files_failed']}")
            if result['errors']:
                print(f"  Errors: {len(result['errors'])}")
        
        except Exception as e:
            display_name = artist_data.get('alias') if artist_data.get('alias') else artist_data['name']
            print(f"Error checking artist {display_name}: {e}")
    
    def _run_loop(self) -> None:
        """Main scheduler loop"""
        print("Scheduler loop started")
        
        while self.running:
            try:
                now = datetime.now()
                artists = self.artist_manager.get_all_artists()
                
                for artist in artists:
                    artist_id = artist['id']
                    
                    # Get timer (artist-specific or global)
                    timer = artist.get('timer')
                    if not timer:
                        # Use global timer from config
                        continue
                    
                    # Calculate next run time if not set
                    if artist_id not in self.next_run_times:
                        self.next_run_times[artist_id] = self._calculate_next_run(timer)
                    
                    # Check if it's time to run
                    if now >= self.next_run_times[artist_id]:
                        display_name = artist.get('alias') if artist.get('alias') else artist['name']
                        print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] Scheduled check for: {display_name}")
                        self._check_and_download(artist)
                        
                        # Calculate next run time
                        self.next_run_times[artist_id] = self._calculate_next_run(timer)
                        print(f"Next check scheduled for: {self.next_run_times[artist_id].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Sleep for 60 seconds before next check
                time.sleep(60)
            
            except Exception as e:
                print(f"Error in scheduler loop: {e}")
                time.sleep(60)
        
        print("Scheduler loop ended")
