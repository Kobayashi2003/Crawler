# Video Game Music Downloader

A Python tool for downloading video game music from KHInsider using Selenium WebDriver.

## Features

- Automatic browser detection (Chrome, Edge, Firefox)
- Support for MP3 and FLAC formats
- Download album booklet images and artwork
- Organized downloads by CD and format with proper track numbering
- Resume capability (skips existing files)
- Configurable delays to be respectful to servers
- Command-line interface

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure you have at least one of these browsers installed:
   - Google Chrome
   - Microsoft Edge
   - Mozilla Firefox

The tool will automatically download and manage the appropriate WebDriver.

## Usage

### Basic Usage
```bash
python main.py "https://downloads.khinsider.com/game-soundtracks/album/album-name"
```

### Advanced Options
```bash
# Download only MP3 files
python main.py -f mp3 "https://downloads.khinsider.com/game-soundtracks/album/album-name"

# Download only FLAC files
python main.py -f flac "https://downloads.khinsider.com/game-soundtracks/album/album-name"

# Specify output directory
python main.py -o "my_music" "https://downloads.khinsider.com/game-soundtracks/album/album-name"

# Use specific browser
python main.py -b chrome "https://downloads.khinsider.com/game-soundtracks/album/album-name"

# Run in headless mode (no browser window)
python main.py --headless "https://downloads.khinsider.com/game-soundtracks/album/album-name"

# Skip downloading booklet images
python main.py --no-booklet "https://downloads.khinsider.com/game-soundtracks/album/album-name"
```

### Command Line Options

- `-o, --output`: Output directory (default: downloads)
- `-f, --format`: Audio format - mp3, flac, or both (default: both)
- `-b, --browser`: Browser to use - chrome, edge, firefox, or auto (default: auto)
- `--headless`: Run browser in headless mode
- `--no-booklet`: Skip downloading booklet images

## Example

```bash
python main.py "https://downloads.khinsider.com/game-soundtracks/album/pulltop-vocal-collection-uta-no-kanzume"
```

This will:
1. Create a folder named after the album in the downloads directory
2. Download all available MP3 and FLAC files organized by format and CD
3. Download booklet images to a "Booklet" subfolder
4. Use proper track numbering (01. Song Title.mp3)

## File Organization

Downloads are organized as:

**Multi-CD Albums:**
```
downloads/
└── Album Name/
    ├── Booklet/
    │   ├── 00 Box Front.jpg
    │   └── 01 Box Back.jpg
    └── Music/
        ├── MP3/
        │   ├── CD1/
        │   │   ├── 01. Go With Me!.mp3
        │   │   └── 02. Kitto, Zutto.mp3
        │   └── CD2/
        │       └── 01. Dissonant Chord.mp3
        └── FLAC/
            ├── CD1/
            │   ├── 01. Go With Me!.flac
            │   └── 02. Kitto, Zutto.flac
            └── CD2/
                └── 01. Dissonant Chord.flac
```

**Single CD Albums:**
```
downloads/
└── Album Name/
    ├── Booklet/
    │   ├── 00 Box Front.jpg
    │   └── 01 Box Back.jpg
    └── Music/
        ├── MP3/
        │   ├── 01. jewelry days -Short Version-.mp3
        │   ├── 02. Grand Destiny ～Big Festival MIX～.mp3
        │   └── ...
        └── FLAC/
            ├── 01. jewelry days -Short Version-.flac
            ├── 02. Grand Destiny ～Big Festival MIX～.flac
            └── ...
```

## Notes

- The tool includes delays between requests to be respectful to the server
- Existing files are automatically skipped
- The browser window will open during operation (unless using --headless)
- WebDrivers are automatically downloaded and managed
- Tracks are automatically organized by CD number and formatted with proper numbering