# khinsider-downloader

A downloader for [KHInsider](https://downloads.khinsider.com). Downloads video game music albums with support for MP3/FLAC formats, booklet images, and multi-CD organization.

## Installation

```bash
pip install -r requirements.txt
```

A supported browser (Chrome, Edge, or Firefox) is required. WebDrivers are managed automatically.

## Usage

```bash
python main.py <album_url> [options]
```

Example:

```bash
python main.py "https://downloads.khinsider.com/game-soundtracks/album/album-name"
```

### Options

- `-o, --output`: Output directory (default: `downloads`)
- `-f, --format`: Audio format — `mp3`, `flac`, or `both` (default: `both`)
- `-b, --browser`: Browser to use — `chrome`, `edge`, `firefox`, or `auto` (default: `auto`)
- `--headless`: Run browser in headless mode
- `--no-booklet`: Skip downloading booklet images
