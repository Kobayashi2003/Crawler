# Auto Kemono Downloader

An automated monitoring and downloading system for Kemono artists. This tool periodically checks for new posts from configured artists and automatically downloads them based on customizable filters and schedules.

## Features

- **Automated Monitoring**: Schedule periodic checks for artist updates (daily, weekly, or monthly)
- **Per-Artist Configuration**: Customize download settings and schedules for each artist
- **Flexible Filtering**: Filter posts by keywords, date ranges, and file types
- **Interactive CLI**: Manage artists and settings while the system is running
- **Resume Support**: Automatically resume interrupted downloads
- **Customizable Naming**: Configure folder and file naming patterns

## Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Quick Start

1. Run the application:
```bash
python main.py
```

2. Add an artist to monitor (just paste their Kemono URL):
```
> add
Artist URL: https://kemono.cr/fanbox/user/25877697
```

3. List monitored artists:
```
> list
```

4. The scheduler will automatically check for updates based on the configured timer.

## Configuration

### Global Configuration (config.json)

The `config.json` file contains global settings that apply to all artists unless overridden:

```json
{
  "download_dir": "I:/kemono",
  "date_format": "%Y.%m.%d",
  "artist_folder_format": "{name}",
  "post_folder_format": "[{published}] {title}",
  "file_name_format": "{idx}",
  "rename_images_only": true,
  "char_replacement": {
    "/": "／",
    "\\": "＼",
    ":": "："
  },
  "save_content_to_file": true,
  "global_timer": {
    "type": "daily",
    "time": "02:00"
  }
}
```

#### Configuration Options

- **download_dir**: Base directory for downloads
- **date_format**: Python strftime format for dates
- **artist_folder_format**: Template for artist folder names
  - Variables: `{name}`, `{service}`, `{id}`
- **post_folder_format**: Template for post folder names
  - Variables: `{id}`, `{title}`, `{published}`
- **file_name_format**: Template for file names
  - Variables: `{idx}`, `{name}`
- **rename_images_only**: Only rename image files (true/false)
- **char_replacement**: Character replacement map for illegal filename characters
- **save_content_to_file**: Save post content to content.txt (true/false)
- **global_timer**: Default schedule for all artists

### Artist Configuration (artists.json)

Artists are stored in `artists.json`. Each artist can have:

```json
{
  "artists": [
    {
      "id": "unique-id",
      "name": "Artist Name",
      "alias": "MyAlias",
      "service": "patreon",
      "user_id": "12345",
      "url": "https://kemono.cr/patreon/user/12345",
      "last_post_date": "2024-01-15T00:00:00",
      "timer": {
        "type": "daily",
        "time": "14:30"
      },
      "use_global_filter": true,
      "config_override": {
        "post_folder_format": "{title}"
      },
      "filter": {
        "keywords": ["artwork"],
        "exclude_keywords": ["sketch"]
      }
    }
  ]
}
```

- **name**: Artist's real name (fetched from profile)
- **alias**: Optional display name (used in UI and folder names if set)

## Timer Configuration

Timers can be set globally or per-artist. Three types are supported:

### Daily
```json
{
  "type": "daily",
  "time": "02:00"
}
```
Runs every day at the specified time.

### Weekly
```json
{
  "type": "weekly",
  "time": "14:30",
  "day": 0
}
```
Runs on a specific day of the week (0=Monday, 6=Sunday) at the specified time.

### Monthly
```json
{
  "type": "monthly",
  "time": "09:00",
  "day": 1
}
```
Runs on a specific day of the month (1-31) at the specified time.

## Filter Configuration

Filters can be configured globally or per-artist. Artist filters work in addition to global filters unless `use_global_filter` is set to false.

### Filter Options

```json
{
  "keywords": ["artwork", "illustration"],
  "exclude_keywords": ["sketch", "WIP"],
  "date_after": "2024-01-01",
  "date_before": "2024-12-31",
  "require_files": true,
  "require_images": false,
  "require_videos": false,
  "require_attachments": false
}
```

- **keywords**: Only download posts containing any of these keywords in the title
- **exclude_keywords**: Skip posts containing any of these keywords
- **date_after**: Only download posts published after this date (YYYY-MM-DD)
- **date_before**: Only download posts published before this date (YYYY-MM-DD)
- **require_files**: Only download posts with any files
- **require_images**: Only download posts with images
- **require_videos**: Only download posts with videos
- **require_attachments**: Only download posts with attachments

## CLI Commands

- **add** - Add a new artist to monitor
- **remove** - Remove an artist from monitoring
- **list** - List all monitored artists
- **timer** - Set timer for an artist or globally
- **config** - View configuration (edit config.json manually)
- **check** - Manually check an artist for updates
- **help** - Show available commands
- **exit/quit** - Exit the program

## Usage Examples

### Adding an Artist

```
> add
Artist URL (e.g., https://kemono.cr/fanbox/user/25877697): https://kemono.cr/patreon/user/12345
Parsed: patreon/user/12345
Fetching artist profile...
Found artist: ExampleArtist
Alias (optional, press Enter to use 'ExampleArtist'): MyAlias
Last post date (YYYY-MM-DDTHH:MM:SS or empty for all): 2024-01-01T00:00:00
Set custom timer? (y/n): y
Timer type:
  1. Daily
  2. Weekly
  3. Monthly
Choice (1/2/3): 1
Time (HH:MM): 14:00
```

Simply paste the artist's Kemono URL. The system automatically:
- Parses the URL to extract service and user ID
- Fetches the artist's name from their profile
- You can optionally provide an alias for display purposes

### Setting a Global Timer

```
> timer
--- Set Timer ---
1. Set global timer
2. Set artist-specific timer
Choice (1/2): 1
Timer type:
  1. Daily
  2. Weekly
  3. Monthly
Choice (1/2/3): 1
Time (HH:MM): 02:00
```

### Manually Checking an Artist

```
> check
Select artist to check:
  1. ExampleArtist
Number: 1
```

## Directory Structure

```
auto-kemono-downloader/
├── main.py                 # Entry point
├── cli.py                  # CLI interface
├── artist_manager.py       # Artist management
├── config_manager.py       # Configuration management
├── filter_manager.py       # Filter logic
├── download_manager.py     # Download orchestration
├── scheduler.py            # Scheduling logic
├── api.py                  # Kemono API
├── session.py              # Session management
├── download.py             # File download
├── utils.py                # Utilities
├── requirements.txt        # Dependencies
├── config.json             # Global configuration
├── artists.json            # Artist configurations
└── README.md               # This file
```

## Notes

- The scheduler checks every 60 seconds if any artist is due for an update
- Downloads are performed sequentially to avoid overwhelming the server
- Partial downloads are automatically resumed if interrupted
- All dates are in ISO format (YYYY-MM-DDTHH:MM:SS)
- The system continues accepting commands while downloads are in progress

## Troubleshooting

### Session Initialization Failed
If you see "Session initialization failed", the system will continue but may encounter access restrictions. This is usually temporary.

### Downloads Failing
- Check your internet connection
- Verify the artist URL is correct
- Check if the Kemono server is accessible

### Timer Not Triggering
- Verify the timer configuration is valid
- Check that the scheduler is running (it starts automatically)
- Ensure the next run time hasn't passed

## License

This tool is for personal use only. Respect the artists and the Kemono platform's terms of service.
