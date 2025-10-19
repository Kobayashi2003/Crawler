#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Command Line Interface
"""

import sys

from config import DEFAULT_DOWNLOAD_DIR
from download import retry_failed_downloads
from downloader import (
    download_single_post,
    download_all_posts,
    download_specific_page,
    download_page_range
)
from session import KemonoSession


# ============================================================================
# UI Display
# ============================================================================

def print_menu():
    """Display main menu"""
    print("\n" + "="*60)
    print(" "*20 + "Kemono Downloader")
    print("="*60)
    print("1. Download Single Post (enter Post URL)")
    print("2. Download All Posts from Profile (enter Profile URL)")
    print("3. Download Specific Page (enter Profile URL + offset)")
    print("4. Download Page Range (enter Profile URL + range)")
    print("5. Exit")
    print("="*60)


# ============================================================================
# User Input
# ============================================================================

def get_download_directory():
    """Prompt user for download directory"""
    print(f"\nDefault download directory: {DEFAULT_DOWNLOAD_DIR}")
    custom_dir = input("Enter custom download directory (press Enter for default): ").strip()
    
    if custom_dir:
        print(f"Using custom directory: {custom_dir}")
        return custom_dir
    else:
        print(f"Using default directory: {DEFAULT_DOWNLOAD_DIR}")
        return None


# ============================================================================
# Retry Handling
# ============================================================================

def handle_retry_prompt(session, results):
    """Handle retry prompt for failed downloads"""
    if not results or not results.get('failed'):
        return True
    
    failed_count = len(results['failed'])
    
    while failed_count > 0:
        print(f"\n{'='*60}")
        print(f"Detected {failed_count} failed download(s)")
        print(f"{'='*60}")
        
        retry = input("Retry failed downloads? (y/n): ").strip().lower()
        
        if retry != 'y':
            print("Skipping retry")
            break
        
        retry_results = retry_failed_downloads(session, results['failed'])
        
        print(f"\n{'='*60}")
        print(f"Retry complete!")
        print(f"Success: {retry_results['success']}/{retry_results['total']} files")
        print(f"Failed: {len(retry_results['failed'])} files")
        print(f"{'='*60}")
        
        results['failed'] = retry_results['failed']
        failed_count = len(retry_results['failed'])
        
        if failed_count == 0:
            print("\n✓ All files downloaded successfully!")
            break
    
    return True


# ============================================================================
# Main Loop
# ============================================================================

def _init_session():
    """Initialize session with UTF-8 encoding"""
    if sys.platform.startswith('win'):
        try:
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
        except:
            pass
    
    print("\n" + "="*60)
    print(" "*15 + "Kemono Downloader Starting...")
    print("="*60)
    print("\nInitializing session...")
    
    try:
        session = KemonoSession()
        print("✓ Session initialization complete\n")
        return session
    except Exception as e:
        print(f"✗ Session initialization failed: {e}")
        print("Program will exit")
        return None


def _handle_single_post(session):
    """Handle single post download"""
    url = input("\nEnter Post URL: ").strip()
    if not url:
        print("✗ URL cannot be empty")
        return
    
    download_dir = get_download_directory()
    
    try:
        results = download_single_post(session, url, download_dir)
        handle_retry_prompt(session, results)
    except Exception as e:
        print(f"\n✗ Operation failed: {e}")


def _handle_all_posts(session):
    """Handle all posts download"""
    url = input("\nEnter Profile URL: ").strip()
    if not url:
        print("✗ URL cannot be empty")
        return
    
    confirm = input("\nThis will download all posts from this profile. Confirm? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled")
        return
    
    download_dir = get_download_directory()
    
    try:
        results = download_all_posts(session, url, download_dir)
        handle_retry_prompt(session, results)
    except Exception as e:
        print(f"\n✗ Operation failed: {e}")


def _handle_specific_page(session):
    """Handle specific page download"""
    url = input("\nEnter Profile URL: ").strip()
    if not url:
        print("✗ URL cannot be empty")
        return
    
    offset_str = input("Enter page offset (0, 50, 100, ...): ").strip()
    try:
        offset = int(offset_str)
        if offset < 0:
            print("✗ Offset cannot be negative")
            return
        
        download_dir = get_download_directory()
        results = download_specific_page(session, url, offset, download_dir)
        handle_retry_prompt(session, results)
    except ValueError:
        print("✗ Offset must be a number")
    except Exception as e:
        print(f"\n✗ Operation failed: {e}")


def _handle_page_range(session):
    """Handle page range download"""
    url = input("\nEnter Profile URL: ").strip()
    if not url:
        print("✗ URL cannot be empty")
        return
    
    range_str = input("Enter range (e.g., 0-150, start-200, 50-end): ").strip()
    if not range_str:
        print("✗ Range cannot be empty")
        return
    
    download_dir = get_download_directory()
    
    try:
        results = download_page_range(session, url, range_str, download_dir)
        handle_retry_prompt(session, results)
    except Exception as e:
        print(f"\n✗ Operation failed: {e}")


def main():
    """Main entry point"""
    session = _init_session()
    if not session:
        return
    
    while True:
        try:
            print_menu()
            choice = input("\nSelect operation (1-5): ").strip()
            
            if choice == '1':
                _handle_single_post(session)
            elif choice == '2':
                _handle_all_posts(session)
            elif choice == '3':
                _handle_specific_page(session)
            elif choice == '4':
                _handle_page_range(session)
            elif choice == '5':
                print("\nThank you for using Kemono Downloader!")
                print("Goodbye!\n")
                break
            else:
                print("\n✗ Invalid choice, please enter 1-5")
            
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n\nInterrupt signal detected")
            confirm = input("Confirm exit? (y/n): ").strip().lower()
            if confirm == 'y':
                print("\nGoodbye!\n")
                break
        except Exception as e:
            print(f"\n✗ Unexpected error occurred: {e}")
            input("\nPress Enter to continue...")


if __name__ == '__main__':
    main()
