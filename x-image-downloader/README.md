# x-image-downloader

A downloader for [X (Twitter)](https://x.com). Scrapes and downloads images from a user's timeline using Playwright, with automatic deduplication and logging.

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

1. Export your X/Twitter cookies to `cookies.json` (browser export format supported)
2. Edit the target user URL in `src/downloader.py`
3. Run:

```bash
python main.py
```

Images are saved to the `images/` directory, organized by author. A `log.json` file tracks downloaded posts to avoid duplicates.
