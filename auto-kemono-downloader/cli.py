#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Command-Line Interface
"""

from typing import Optional

from api import fetch_user_profile
from artist_manager import ArtistManager
from config_manager import ConfigManager
from scheduler import Scheduler
from session import KemonoSession
from utils import parse_artist_url


class CLI:
    """Command-line interface for user interaction"""
    
    def __init__(self, artist_manager: ArtistManager, 
                 config_manager: ConfigManager,
                 scheduler: Scheduler):
        """Initialize CLI"""
        self.artist_manager = artist_manager
        self.config_manager = config_manager
        self.scheduler = scheduler
        self.running = False
    
    def start(self) -> None:
        """Start accepting user input"""
        self.running = True
        self._print_welcome()
        
        while self.running:
            try:
                command = input("\n> ").strip()
                if command:
                    self._process_command(command)
            except KeyboardInterrupt:
                print("\n\nShutting down...")
                self.running = False
            except EOFError:
                self.running = False
            except Exception as e:
                print(f"Error: {e}")
    
    def _print_welcome(self) -> None:
        """Print welcome message"""
        print("\n" + "="*60)
        print("Auto Kemono Downloader")
        print("="*60)
        print("Type 'help' for available commands")
    
    def _process_command(self, command: str) -> None:
        """Process user command"""
        parts = command.lower().split()
        cmd = parts[0] if parts else ""
        
        if cmd == "help":
            self._cmd_help()
        elif cmd == "add":
            self._cmd_add_artist()
        elif cmd == "remove":
            self._cmd_remove_artist()
        elif cmd == "list":
            self._cmd_list_artists()
        elif cmd == "timer":
            self._cmd_set_timer()
        elif cmd == "config":
            self._cmd_update_config()
        elif cmd == "check":
            self._cmd_check_now()
        elif cmd == "check-all":
            self._cmd_check_all()
        elif cmd == "exit" or cmd == "quit":
            self.running = False
        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for available commands")
    
    def _cmd_help(self) -> None:
        """Display help information"""
        print("\nAvailable commands:")
        print("  add        - Add a new artist to monitor")
        print("  remove     - Remove an artist from monitoring")
        print("  list       - List all monitored artists")
        print("  timer      - Set timer for an artist or globally")
        print("  config     - Update configuration")
        print("  check      - Manually check an artist for updates")
        print("  check-all  - Check all artists for updates")
        print("  help       - Show this help message")
        print("  exit/quit  - Exit the program")
    
    def _cmd_add_artist(self) -> None:
        """Add a new artist"""
        print("\n--- Add New Artist ---")
        
        try:
            # Get artist URL
            url = input("Artist URL (e.g., https://kemono.cr/fanbox/user/25877697): ").strip()
            if not url:
                print("URL is required")
                return
            
            # Parse URL to extract service and user_id
            try:
                service, user_id = parse_artist_url(url)
                print(f"Parsed: {service}/user/{user_id}")
            except ValueError as e:
                print(f"Error: {e}")
                return
            
            # Fetch artist profile to get name
            print("Fetching artist profile...")
            try:
                session = KemonoSession()
                profile = fetch_user_profile(session, service, user_id)
                artist_name = profile.get('name', 'Unknown Artist')
                print(f"Found artist: {artist_name}")
            except Exception as e:
                print(f"Warning: Could not fetch profile: {e}")
                artist_name = input("Enter artist name manually: ").strip()
                if not artist_name:
                    print("Artist name is required")
                    return
            
            # Ask for alias
            alias = input(f"Alias (optional, press Enter to use '{artist_name}'): ").strip()
            
            last_date = input("Last post date (YYYY-MM-DDTHH:MM:SS or empty for all): ").strip()
            last_date = last_date if last_date else None
            
            # Ask about timer
            use_timer = input("Set custom timer? (y/n): ").strip().lower()
            timer = None
            if use_timer == 'y':
                timer = self._input_timer()
            
            # Add artist
            artist_id = self.artist_manager.add_artist(
                name=artist_name,
                service=service,
                user_id=user_id,
                alias=alias if alias else None,
                last_post_date=last_date,
                timer=timer
            )
            
            print(f"\n✓ Artist added successfully (ID: {artist_id})")
        
        except KeyboardInterrupt:
            print("\nCancelled")
        except Exception as e:
            print(f"Error adding artist: {e}")
    
    def _cmd_remove_artist(self) -> None:
        """Remove an artist"""
        print("\n--- Remove Artist ---")
        
        # List artists first
        artists = self.artist_manager.get_all_artists()
        if not artists:
            print("No artists to remove")
            return
        
        print("\nCurrent artists:")
        for i, artist in enumerate(artists, 1):
            display_name = artist.get('alias') if artist.get('alias') else artist['name']
            print(f"  {i}. {display_name} ({artist['service']}/{artist['user_id']})")
        
        try:
            choice = input("\nEnter number to remove (or 'cancel'): ").strip()
            if choice.lower() == 'cancel':
                return
            
            idx = int(choice) - 1
            if 0 <= idx < len(artists):
                artist = artists[idx]
                confirm = input(f"Remove '{artist['name']}'? (y/n): ").strip().lower()
                if confirm == 'y':
                    self.artist_manager.remove_artist(artist['id'])
            else:
                print("Invalid choice")
        
        except ValueError:
            print("Invalid input")
        except Exception as e:
            print(f"Error: {e}")
    
    def _cmd_list_artists(self) -> None:
        """List all artists"""
        artists = self.artist_manager.get_all_artists()
        
        if not artists:
            print("\nNo artists configured")
            return
        
        print(f"\n{'='*60}")
        print(f"Monitored Artists ({len(artists)})")
        print(f"{'='*60}")
        
        for artist in artists:
            display_name = artist.get('alias') if artist.get('alias') else artist['name']
            print(f"\nName: {display_name}")
            if artist.get('alias'):
                print(f"  (Real name: {artist['name']})")
            print(f"  Service: {artist['service']}")
            print(f"  User ID: {artist['user_id']}")
            print(f"  URL: {artist['url']}")
            print(f"  Last post date: {artist.get('last_post_date', 'None')}")
            
            timer = artist.get('timer')
            if timer:
                print(f"  Timer: {timer['type']} at {timer.get('time', 'N/A')}")
            else:
                print(f"  Timer: Using global")
    
    def _cmd_set_timer(self) -> None:
        """Set timer for artist or globally"""
        print("\n--- Set Timer ---")
        print("1. Set global timer")
        print("2. Set artist-specific timer")
        
        try:
            choice = input("Choice (1/2): ").strip()
            
            if choice == '1':
                timer = self._input_timer()
                if timer:
                    self.config_manager.update_global_config(global_timer=timer)
                    print("✓ Global timer updated")
            
            elif choice == '2':
                artists = self.artist_manager.get_all_artists()
                if not artists:
                    print("No artists configured")
                    return
                
                print("\nSelect artist:")
                for i, artist in enumerate(artists, 1):
                    display_name = artist.get('alias') if artist.get('alias') else artist['name']
                    print(f"  {i}. {display_name}")
                
                idx = int(input("Number: ").strip()) - 1
                if 0 <= idx < len(artists):
                    timer = self._input_timer()
                    if timer:
                        self.artist_manager.update_artist(artists[idx]['id'], timer=timer)
                        print("✓ Artist timer updated")
                else:
                    print("Invalid choice")
        
        except Exception as e:
            print(f"Error: {e}")
    
    def _input_timer(self) -> Optional[dict]:
        """Input timer configuration"""
        print("\nTimer type:")
        print("  1. Daily")
        print("  2. Weekly")
        print("  3. Monthly")
        
        try:
            timer_type = input("Choice (1/2/3): ").strip()
            
            if timer_type == '1':
                time_str = input("Time (HH:MM): ").strip()
                return {"type": "daily", "time": time_str}
            
            elif timer_type == '2':
                time_str = input("Time (HH:MM): ").strip()
                day = int(input("Day of week (0=Mon, 6=Sun): ").strip())
                return {"type": "weekly", "time": time_str, "day": day}
            
            elif timer_type == '3':
                time_str = input("Time (HH:MM): ").strip()
                day = int(input("Day of month (1-31): ").strip())
                return {"type": "monthly", "time": time_str, "day": day}
            
            else:
                print("Invalid choice")
                return None
        
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def _cmd_update_config(self) -> None:
        """Update configuration"""
        print("\n--- Update Configuration ---")
        print("Current configuration:")
        config = self.config_manager.get_global_config()
        print(f"  Download directory: {config.get('download_dir')}")
        print(f"  Date format: {config.get('date_format')}")
        print(f"  Artist folder format: {config.get('artist_folder_format')}")
        print(f"  Post folder format: {config.get('post_folder_format')}")
        print("\n(Configuration editing not fully implemented)")
        print("Edit config.json manually for now")
    
    def _cmd_check_now(self) -> None:
        """Manually check an artist"""
        artists = self.artist_manager.get_all_artists()
        
        if not artists:
            print("No artists configured")
            return
        
        print("\nSelect artist to check:")
        for i, artist in enumerate(artists, 1):
            display_name = artist.get('alias') if artist.get('alias') else artist['name']
            print(f"  {i}. {display_name}")
        
        try:
            idx = int(input("Number: ").strip()) - 1
            if 0 <= idx < len(artists):
                print(f"\nChecking {artists[idx]['name']}...")
                self.scheduler._check_and_download(artists[idx])
            else:
                print("Invalid choice")
        except Exception as e:
            print(f"Error: {e}")
    
    def _cmd_check_all(self) -> None:
        """Manually check all artists for updates"""
        artists = self.artist_manager.get_all_artists()
        
        if not artists:
            print("No artists configured")
            return
        
        print(f"\n{'='*60}")
        print(f"Checking all {len(artists)} artists for updates")
        print(f"{'='*60}")
        
        for i, artist in enumerate(artists, 1):
            display_name = artist.get('alias') if artist.get('alias') else artist['name']
            print(f"\n[{i}/{len(artists)}] Checking: {display_name}")
            try:
                self.scheduler._check_and_download(artist)
            except Exception as e:
                print(f"✗ Error checking {display_name}: {e}")
        
        print(f"\n{'='*60}")
        print(f"Completed checking all artists")
        print(f"{'='*60}")
