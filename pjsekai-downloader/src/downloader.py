#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Sekai Character Image Downloader
Download all character images from pjsekai.gamedbs.jp
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path


class PjsekaiDownloader:
    def __init__(self, output_dir="downloads"):
        self.base_url = "https://pjsekai.gamedbs.jp"
        self.output_dir = Path(output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_filename(self, filename):
        """Clean illegal characters from filename"""
        illegal_chars = r'[<>:"/\\|?*]'
        filename = re.sub(illegal_chars, '_', filename)
        return filename.strip()

    def download_image(self, img_url, save_path):
        """Download a single image"""
        try:
            if save_path.exists():
                return False  # Already exists, skip

            response = self.session.get(img_url, timeout=30)
            response.raise_for_status()

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)

            print(f"  ✓ {save_path.name}")
            return True

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return False

    def get_all_characters(self):
        """Get all characters from homepage"""
        print("Fetching character list...")
        url = f"{self.base_url}/"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            characters = []
            pattern = re.compile(r'^https?://[^/]+/chara/show/\d+$')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                if pattern.match(full_url):
                    match = re.search(r'/chara/show/(\d+)$', href)
                    if match:
                        characters.append(match.group(1))

            characters = sorted(list(set(characters)), key=int)
            print(f"Found {len(characters)} characters\n")
            return characters

        except Exception as e:
            print(f"Failed to get character list: {e}")
            return []

    def get_character_name(self, soup, char_id):
        """Extract character name from page"""
        title = soup.find('h3', class_='uk-heading-line')
        if title:
            title_text = title.get_text(strip=True)
            match = re.search(r'】\s*(.+?)\s+(?:情報|メンバー)', title_text)
            if match:
                return self.sanitize_filename(match.group(1))
        return f"Character_{char_id}"

    def download_profile_images(self, soup, char_dir):
        """Download profile images"""
        profile_images = soup.find_all('img', src=re.compile(r'/image/chara/img/'))
        if not profile_images:
            return 0

        print("  Profile images:")
        total = 0
        for i, img in enumerate(profile_images, 1):
            img_url = urljoin(self.base_url, img['src'])
            ext = Path(urlparse(img_url).path).suffix
            save_path = char_dir / "profile" / f"profile{i}{ext}"
            if self.download_image(img_url, save_path):
                total += 1
            time.sleep(0.3)
        return total

    def download_stamps(self, soup, char_dir):
        """Download stamp images"""
        stamp_images = soup.find_all('img', src=re.compile(r'/image/chara/stp/'))
        stamp_images += soup.find_all('img', attrs={'data-src': re.compile(r'/image/chara/stp/')})
        stamp_links = soup.find_all('a', href=re.compile(r'/image/chara/stp/'))

        if not stamp_images and not stamp_links:
            return 0

        print("  Stamps:")
        total = 0
        seen_urls = set()
        count = 1

        for img in stamp_images:
            img_url = img.get('src') or img.get('data-src')
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                img_url = urljoin(self.base_url, img_url)
                ext = Path(urlparse(img_url).path).suffix
                save_path = char_dir / "stamps" / f"stamp{count}{ext}"
                if self.download_image(img_url, save_path):
                    total += 1
                    count += 1
                time.sleep(0.3)

        for link in stamp_links:
            img_url = link.get('href')
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                img_url = urljoin(self.base_url, img_url)
                ext = Path(urlparse(img_url).path).suffix
                save_path = char_dir / "stamps" / f"stamp{count}{ext}"
                if self.download_image(img_url, save_path):
                    total += 1
                    count += 1
                time.sleep(0.3)

        return total

    def download_sd_characters(self, soup, char_dir):
        """Download SD character images"""
        sd_images = soup.find_all('img', attrs={'data-src': re.compile(r'/image/chara/sdc/')})
        sd_links = soup.find_all('a', href=re.compile(r'/image/chara/sdc/'))

        if not sd_images and not sd_links:
            return 0

        print("  SD characters:")
        total = 0
        seen_urls = set()
        count = 1

        for img in sd_images:
            img_url = img.get('data-src')
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                img_url = urljoin(self.base_url, img_url)
                ext = Path(urlparse(img_url).path).suffix
                save_path = char_dir / "sd_characters" / f"sd{count}{ext}"
                if self.download_image(img_url, save_path):
                    total += 1
                    count += 1
                time.sleep(0.3)

        for link in sd_links:
            img_url = link.get('href')
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                img_url = urljoin(self.base_url, img_url)
                ext = Path(urlparse(img_url).path).suffix
                save_path = char_dir / "sd_characters" / f"sd{count}{ext}"
                if self.download_image(img_url, save_path):
                    total += 1
                    count += 1
                time.sleep(0.3)

        return total

    def download_3d_models(self, soup, char_dir):
        """Download 3D model images"""
        model_images = soup.find_all('img', attrs={'data-src': re.compile(r'/image/chara/3d[cs]/')})
        model_links = soup.find_all('a', href=re.compile(r'/image/chara/3d[cs]/'))

        if not model_images and not model_links:
            return 0

        print("  3D models:")
        total = 0
        seen_urls = set()
        count = 1

        for img in model_images:
            img_url = img.get('data-src')
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                img_url = urljoin(self.base_url, img_url)
                ext = Path(urlparse(img_url).path).suffix
                save_path = char_dir / "3d_models" / f"3d_model{count}{ext}"
                if self.download_image(img_url, save_path):
                    total += 1
                    count += 1
                time.sleep(0.3)

        for link in model_links:
            img_url = link.get('href')
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                img_url = urljoin(self.base_url, img_url)
                ext = Path(urlparse(img_url).path).suffix
                save_path = char_dir / "3d_models" / f"3d_model{count}{ext}"
                if self.download_image(img_url, save_path):
                    total += 1
                    count += 1
                time.sleep(0.3)

        return total

    def download_comics(self, soup, char_dir):
        """Download 1-panel comic images"""
        comic_images = soup.find_all('img', attrs={'data-src': re.compile(r'/image/chara/cm1/')})
        comic_links = soup.find_all('a', href=re.compile(r'/image/chara/cm1/'))

        if not comic_images and not comic_links:
            return 0

        print("  Comics:")
        total = 0
        seen_urls = set()
        count = 1

        for img in comic_images:
            img_url = img.get('data-src')
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                img_url = urljoin(self.base_url, img_url)
                ext = Path(urlparse(img_url).path).suffix
                save_path = char_dir / "comics" / f"comic{count}{ext}"
                if self.download_image(img_url, save_path):
                    total += 1
                    count += 1
                time.sleep(0.3)

        for link in comic_links:
            img_url = link.get('href')
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                img_url = urljoin(self.base_url, img_url)
                ext = Path(urlparse(img_url).path).suffix
                save_path = char_dir / "comics" / f"comic{count}{ext}"
                if self.download_image(img_url, save_path):
                    total += 1
                    count += 1
                time.sleep(0.3)

        return total

    def download_cards(self, soup, char_dir, char_id):
        """Download card images from card detail pages"""
        card_links = soup.find_all('a', href=re.compile(rf'/chara/show/{char_id}/\d+'))
        if not card_links:
            return 0

        print(f"  Cards ({len(card_links)} found):")
        total = 0

        for link in card_links:
            card_url = urljoin(self.base_url, link['href'])
            card_name = link.get_text(strip=True)
            card_name = self.sanitize_filename(card_name) if card_name else "Unknown"

            count = self.download_card_images(card_url, char_dir, card_name)
            total += count
            time.sleep(1)

        return total

    def download_character_images(self, char_id):
        """Download all images for a specific character"""
        char_url = f"{self.base_url}/chara/show/{char_id}"

        try:
            response = self.session.get(char_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Get character name
            char_name = self.get_character_name(soup, char_id)

            # Create character directory
            char_dir = self.output_dir / char_name

            # Skip if character folder already exists
            if char_dir.exists():
                print(f"[{char_id}] {char_name} - Already downloaded, skipping")
                return 0

            print(f"[{char_id}] {char_name}")
            char_dir.mkdir(parents=True, exist_ok=True)

            # Download all image types
            total = 0
            total += self.download_profile_images(soup, char_dir)
            total += self.download_stamps(soup, char_dir)
            total += self.download_sd_characters(soup, char_dir)
            total += self.download_3d_models(soup, char_dir)
            total += self.download_comics(soup, char_dir)
            total += self.download_cards(soup, char_dir, char_id)

            print(f"  Total: {total} images\n")
            return total

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"[{char_id}] Not found (404)\n")
            else:
                print(f"[{char_id}] HTTP Error: {e}\n")
            return 0
        except Exception as e:
            print(f"[{char_id}] Failed: {e}\n")
            return 0

    def download_card_images(self, card_url, char_dir, card_name):
        """Download images from a card detail page"""
        try:
            response = self.session.get(card_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            downloaded = 0

            # Download main card images
            card_links = soup.find_all('a', href=re.compile(r'/image/chara/member/'))
            for link in card_links:
                img_url = urljoin(self.base_url, link['href'])
                caption = link.get('data-caption', '')
                ext = Path(urlparse(img_url).path).suffix

                if '特訓前' in caption or '特訓前' in link.get_text():
                    filename = f"{card_name}_before{ext}"
                elif '特訓後' in caption or '特訓後' in link.get_text():
                    filename = f"{card_name}_after{ext}"
                else:
                    filename = f"{card_name}{ext}"

                save_path = char_dir / "cards" / filename
                if self.download_image(img_url, save_path):
                    downloaded += 1
                time.sleep(0.3)

            # Download trimmed card images
            trimmed_links = soup.find_all('a', href=re.compile(r'/image/chara/member_trm/'))
            for link in trimmed_links:
                img_url = urljoin(self.base_url, link['href'])
                caption = link.get('data-caption', '')
                ext = Path(urlparse(img_url).path).suffix

                if '特訓前' in caption or '特訓前' in link.get_text():
                    filename = f"{card_name}_before_trimmed{ext}"
                elif '特訓後' in caption or '特訓後' in link.get_text():
                    filename = f"{card_name}_after_trimmed{ext}"
                else:
                    filename = f"{card_name}_trimmed{ext}"

                save_path = char_dir / "cards_trimmed" / filename
                if self.download_image(img_url, save_path):
                    downloaded += 1
                time.sleep(0.3)

            return downloaded

        except Exception as e:
            return 0

    def download_all(self):
        """Download all characters"""
        print("="*60)
        print("Project Sekai Character Image Downloader")
        print("="*60)
        print()

        characters = self.get_all_characters()
        if not characters:
            print("No characters found")
            return

        total_images = 0
        for char_id in characters:
            count = self.download_character_images(char_id)
            total_images += count
            time.sleep(2)

        print("="*60)
        print(f"Completed! Total images: {total_images}")
        print(f"Location: {self.output_dir.absolute()}")
        print("="*60)
