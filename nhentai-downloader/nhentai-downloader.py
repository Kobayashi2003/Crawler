import asyncio
import aiohttp
import aiofiles
import time
import json
from pathlib import Path

class AsyncImageCrawler:
    def __init__(self, base_url="https://pics.hentai.name/", file_ext="webp", download_dir="downloads", cookies=None):
        self.base_url = base_url
        self.file_ext = file_ext
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.cookies = cookies
    
    def get_image_url(self, page_num):
        return f"{self.base_url}{page_num}.{self.file_ext}"
    
    async def download_image(self, session, page_num, semaphore, timeout=30, retry_times=3):
        async with semaphore:
            url = self.get_image_url(page_num)
            filename = f"{page_num}.{self.file_ext}"
            filepath = self.download_dir / filename
            
            if filepath.exists():
                print(f"File already exists, skipping: {filename}")
                return True
            
            for attempt in range(retry_times):
                try:
                    print(f"Downloading: {url}")
                    
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                        # Handle rate limiting
                        if response.status == 429:
                            print(f"Rate limited, waiting 10 seconds before retry...")
                            await asyncio.sleep(10)
                            continue
                        
                        response.raise_for_status()
                        
                        content_type = response.headers.get('content-type', '')
                        if 'image' not in content_type:
                            print(f"Warning: Page {page_num} may not be an image file (content-type: {content_type})")
                        
                        async with aiofiles.open(filepath, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        file_size = filepath.stat().st_size
                        print(f"Download successful: {filename} ({file_size} bytes)")
                        return True
                        
                except Exception as e:
                    print(f"Download failed (attempt {attempt + 1}/{retry_times}): {url}")
                    print(f"Error: {e}")
                    
                    if attempt < retry_times - 1:
                        print(f"Waiting 5 seconds before retry...")
                        await asyncio.sleep(5)
                    else:
                        print(f"Max retry attempts reached, skipping page {page_num}")
                        return False
            
            return False
    
    async def download_batch(self, session, page_list, semaphore):
        """Download a batch of pages"""
        tasks = []
        for page in page_list:
            task = asyncio.create_task(
                self.download_image(session, page, semaphore)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def download_range(self, start_page, end_page, max_concurrent=3, delay=2, batch_size=10, batch_delay=30):
        print(f"Starting image download, page range: {start_page} - {end_page}")
        print(f"Base URL: {self.base_url}")
        print(f"Download directory: {self.download_dir}")
        print(f"Max concurrent downloads: {max_concurrent}")
        print(f"Request delay: {delay} seconds")
        print(f"Batch size: {batch_size}")
        print(f"Batch delay: {batch_delay} seconds")
        if self.cookies:
            print(f"Using cookies: {len(self.cookies)} cookie(s)")
        print("-" * 50)
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/jpeg,image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        connector = aiohttp.TCPConnector(
            limit=max_concurrent, 
            limit_per_host=max_concurrent,
            keepalive_timeout=60,
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=30)
        
        # Create cookie jar if cookies are provided
        cookie_jar = None
        if self.cookies:
            cookie_jar = aiohttp.CookieJar()
            # Add cookies to the jar
            for name, value in self.cookies.items():
                cookie_jar.update_cookies({name: value})
        
        total_success = 0
        total_failed = 0
        
        async with aiohttp.ClientSession(
            headers=headers, 
            connector=connector, 
            timeout=timeout,
            cookie_jar=cookie_jar
        ) as session:
            # Process in batches
            all_pages = list(range(start_page, end_page + 1))
            
            for i in range(0, len(all_pages), batch_size):
                batch_pages = all_pages[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(all_pages) + batch_size - 1) // batch_size
                
                print(f"\nProcessing batch {batch_num}/{total_batches} (pages {batch_pages[0]}-{batch_pages[-1]})")
                
                # Add delay between starting downloads in the batch
                tasks = []
                for j, page in enumerate(batch_pages):
                    if j > 0:  # Add delay between starting downloads
                        await asyncio.sleep(delay)
                    
                    task = asyncio.create_task(
                        self.download_image(session, page, semaphore)
                    )
                    tasks.append(task)
                
                # Wait for batch to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                batch_success = sum(1 for result in results if result is True)
                batch_failed = len(results) - batch_success
                
                total_success += batch_success
                total_failed += batch_failed
                
                print(f"Batch {batch_num} completed: Success: {batch_success}, Failed: {batch_failed}")
                
                # Wait between batches (except for the last batch)
                if i + batch_size < len(all_pages):
                    print(f"Waiting {batch_delay} seconds before next batch...")
                    await asyncio.sleep(batch_delay)
        
        print("-" * 50)
        print(f"Download completed! Total Success: {total_success}, Total Failed: {total_failed}")

def load_cookies_from_file(cookies_file="cookies.json"):
    cookies_path = Path(cookies_file)
    if not cookies_path.exists():
        print(f"Cookies file not found: {cookies_file}")
        return None
    
    try:
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies_data = json.load(f)
        
        # Check if the cookies are in browser export format (array format)
        if isinstance(cookies_data, list):
            cookies = {}
            for cookie in cookies_data:
                if 'name' in cookie and 'value' in cookie:
                    cookies[cookie['name']] = cookie['value']
            print(f"Loaded {len(cookies)} cookies from browser export format in {cookies_file}")
        elif isinstance(cookies_data, dict):
            # Simple key-value format
            cookies = cookies_data
            print(f"Loaded {len(cookies)} cookies from simple format in {cookies_file}")
        else:
            print(f"Unknown cookies format in {cookies_file}")
            return None
            
        return cookies
    except json.JSONDecodeError as e:
        print(f"Error parsing cookies file: {e}")
        return None
    except Exception as e:
        print(f"Error reading cookies file: {e}")
        return None

async def main():
    cookies = load_cookies_from_file("cookies.json")
    
    crawler = AsyncImageCrawler(
        base_url="https://m2.imhentai.xxx/008/yak45fbtvn/",
        file_ext="jpg",
        download_dir="COMIC BAVEL 2017-01 [Digital]",
        cookies=cookies
    )
    
    start_page = 1
    end_page = 403
    
    print(f"Preparing to download pages {start_page} to {end_page}")
    
    start_time = time.time()
    # Conservative settings to avoid being blocked
    await crawler.download_range(
        start_page, 
        end_page, 
        max_concurrent=5,    # Very low concurrency
        delay=1,             # 3 seconds between downloads in same batch
        batch_size=5,        # Only 5 images per batch
        batch_delay=1       # 1 minute between batches
    )
    end_time = time.time()
    
    print(f"Total time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
