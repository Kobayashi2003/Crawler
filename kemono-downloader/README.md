# kemono-downloader

A downloader for [Kemono](https://kemono.cr). Interactive CLI for downloading posts, profiles, and page ranges.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

Follow the prompts to choose an operation:

1. Download a single post (paste Post URL)
2. Download multiple posts (file with URLs or paste URLs)
3. Download all posts from a profile (paste Profile URL)
4. Download a specific page (Profile URL + offset)
5. Download a page range (Profile URL + range like `0-150`)
