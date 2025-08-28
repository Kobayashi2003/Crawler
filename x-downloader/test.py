import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        with open("cookies.json", "r", encoding="utf-8") as f:
            cookies = json.load(f)

            for cookie in cookies:
                if 'sameSite' not in cookie:
                    continue
                cookie['sameSite'] = {'strict': 'Strict', 'Lax': 'lax', 'none': 'None'}.get(cookie['sameSite'])
                if not cookie['sameSite']:
                    del cookie['sameSite']
                
        await context.add_cookies(cookies)

        page = await context.new_page()
        await page.goto("https://x.com/")

        await page.pause()
        await browser.close()

asyncio.run(main())
