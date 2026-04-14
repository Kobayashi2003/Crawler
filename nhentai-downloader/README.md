# nhentai-downloader

A downloader for [nhentai](https://nhentai.net) / [imhentai](https://imhentai.xxx). Batch downloads gallery images with async concurrency and rate limiting.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Edit the configuration in `src/downloader.py` to set:

- `base_url` — Gallery image base URL
- `file_ext` — Image file extension (`jpg`, `webp`, etc.)
- `download_dir` — Output directory name
- `start_page` / `end_page` — Page range to download

Then run:

```bash
python main.py
```

Optionally place a `cookies.json` file in the project root for authenticated access.
