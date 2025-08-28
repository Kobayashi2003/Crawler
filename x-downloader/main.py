import os
import json
import httpx
import random
import asyncio
from datetime import datetime 

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, expect


SAVE_PATH = "images"
LOG_PATH = "log.json"
COOKIES_PATH = "cookies.json"

if not COOKIES_PATH:
    COOKIES_PATH = "cookies.json"

if not os.path.exists(COOKIES_PATH):
    raise FileNotFoundError("cookies.json not found.")

if not LOG_PATH:
    LOG_PATH = "log.json"

if not os.path.exists(LOG_PATH):
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False)

if not SAVE_PATH:
    SAVE_PATH = "images"

if not os.path.exists(SAVE_PATH):
    os.makedirs(SAVE_PATH, exist_ok=True)

async def get_illustrations(context, url):

    with open(COOKIES_PATH, "r", encoding="utf-8") as f:
        cookies = json.load(f)

        for cookie in cookies:
            if 'sameSite' not in cookie:
                continue
            cookie['sameSite'] = {'strict': 'Strict', 'Lax': 'lax', 'none': 'None'}.get(cookie['sameSite'])
            if not cookie['sameSite']:
                del cookie['sameSite']
        
        await context.add_cookies(cookies)

    page = await context.new_page()

    await page.goto(url)
        
    for _ in range(9999):
        await expect(page.locator('article').nth(0)).to_be_visible(timeout=100000)

        article_count = await page.locator('article').count()

        for _ in range(article_count):

            try:
                article = page.locator("article").first
                
                is_repost = await article.locator('[data-testid="socialContext"]').count() > 0
                if is_repost:
                    print("Skipping repost")
                    await article.locator("xpath=../../..").first.evaluate("(element) => element.remove()")
                    await asyncio.sleep(random.randint(1, 3))
                    continue
                    
                soup = BeautifulSoup(await article.inner_html(), "lxml")

                if 'style="text-overflow: unset;">Ad</span>' in str(soup):
                    raise ValueError("This is an advertisement.")
        
                time_element = soup.find("time")
                publish_time = time_element.get("datetime")
                publish_url = "https://x.com" + time_element.find_parent().get("href")

                tweetText = soup.find("div", attrs={"data-testid": "tweetText"})
                publish_content = tweetText.get_text() if tweetText else ""

                tweetPhotos = soup.find_all("div", attrs={"data-testid": "tweetPhoto"})
                publish_images = [img.get("src") for photo in tweetPhotos for img in photo.find_all("img")]
                has_image = len(publish_images) > 0

                author = soup.find("div", attrs={"data-testid": "User-Name"}).find_all('span')[0].get_text()
                author += soup.find("div", attrs={"data-testid": "User-Name"}).find_all('span')[-2].get_text()
        
                print(f"Fetched Article: {publish_url}")
                print(f"Author: {author}")
                print(f"Publish Time: {publish_time}")
                print(f"Content: {publish_content}")
                print(f"Has Image: {has_image}")
                if has_image:
                    print(f"Images Count: {len(publish_images)}")
                    for image in publish_images:
                        print(f"Image: {image}")
                print()

                log = {
                    "url": publish_url,
                    "author": author,
                    "publish_time": publish_time,
                    "content": publish_content,
                    "has_image": has_image,
                    "images": publish_images,
                    "fetched_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    log_data = json.load(f)

                if publish_url in log_data:
                    print(f"Skipping {publish_url} because it already exists.")
                    await article.locator("xpath=../../..").first.evaluate("(element) => element.remove()")
                    await asyncio.sleep(random.randint(1, 2))
                    continue

                log_data[publish_url] = log

                with open(LOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(log_data, f, ensure_ascii=False, indent=2)

                for image in publish_images:
                    image = image[:image.rfind("?")]
                    image_name = image[image.rfind("/") + 1:]
                    image_url = image + "?format=jpg&name=orig"

                    save_folder = author
                    save_path = os.path.join(SAVE_PATH, save_folder)
                    if not os.path.exists(save_path):
                        os.makedirs(save_path, exist_ok=True)

                    save_name = (
                        author + "_" +
                        datetime.strptime(publish_time, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d") + "_" + 
                        image_name + '.jpg'
                    )

                    async with httpx.AsyncClient() as session:
                        response = await session.get(image_url)
                        with open(os.path.join(save_path, save_name), "wb") as f:
                            f.write(response.content)

            except Exception as e:
                print(f"Error: {e}")

            await article.locator("xpath=../../..").first.evaluate("(element) => element.remove()")

            wait_time = random.randint(5, 10)
            await asyncio.sleep(wait_time)

async def main():
    random.seed(datetime.now().timestamp())
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        await asyncio.gather(
            get_illustrations(context, "https://x.com/KuroTuki_nn"),
            # get_illustrations(context, "https://x.com/hitenkei"),
        )

if __name__ == "__main__":
    asyncio.run(main())