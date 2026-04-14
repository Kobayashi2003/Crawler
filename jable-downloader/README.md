# jable-downloader

A downloader for [Jable.tv](https://jable.tv). Downloads videos (with cover images) from individual video pages or all videos from a model's page.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

Select a mode:

1. **Download video(s) by URL** — Enter one or more Jable video URLs to download
2. **Download all videos from a model page** — Enter a model page URL (e.g. `https://jable.tv/models/hikaru-emo/`)

### Model page options

- **Sort order**: `best` (近期最佳), `latest` (最近更新), `views` (最多觀看), `favorites` (最高收藏)
- **Limit**: Maximum number of videos to download
- **Skip confirmation**: Download without previewing the video list
