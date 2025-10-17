# Kemono Downloader

A simplified Kemono content download tool that supports 4 download modes.

## Features

- **Single Post Download**: Download a specific post by URL
- **All Posts Download**: Download all posts from a creator's profile
- **Specific Page Download**: Download posts from a specific page (offset)
- **Page Range Download**: Download posts from a range of pages

## Requirements

```bash
pip install -r requirements.txt
```

Dependencies:
- requests >= 2.31.0
- tqdm >= 4.66.0

## Usage

Run the program:

```bash
python kemono_downloader.py
```

### Menu Options

1. **Download Single Post**: Enter a post URL
   - Example: `https://kemono.cr/fanbox/user/12345/post/67890`

2. **Download All Posts from Profile**: Enter a profile URL
   - Example: `https://kemono.cr/fanbox/user/12345`
   - Downloads all posts from the creator

3. **Download Specific Page**: Enter profile URL + offset
   - Offset values: 0, 50, 100, 150, etc.
   - Each page contains up to 50 posts

4. **Download Page Range**: Enter profile URL + range
   - Examples:
     - `0-150`: Download from offset 0 to 150
     - `start-200`: Download from beginning to offset 200
     - `50-end`: Download from offset 50 to the end

5. **Exit**: Close the program

## File Organization

Downloaded files are organized as follows:

```
kemono/
└── {artist-name}-{service}-{user_id}/
    └── posts/
        └── {post_id}/
            ├── 1-filename.jpg
            ├── 2-filename.png
            └── ...
```

## Features

- **Progress Bar**: Visual progress indicator for each file download
- **Skip Existing Files**: Automatically skips files that are already downloaded
- **Retry Mechanism**: Automatically retries failed requests (up to 3 times)
- **Error Handling**: Graceful error handling with informative messages
- **UTF-8 Support**: Properly handles Unicode filenames

## Configuration

The following constants can be modified at the top of the script:

- `KEMONO_DOMAIN`: Default is "kemono.cr"
- `POSTS_PER_PAGE`: Number of posts per page (default: 50)
- `MAX_RETRIES`: Maximum retry attempts for failed requests (default: 3)
- `RETRY_DELAY_BASE`: Base delay for exponential backoff (default: 5 seconds)

## Notes

- The program adds a 0.5-second delay between post downloads to avoid rate limiting
- Files are downloaded using streaming to minimize memory usage
- Existing files with matching sizes are automatically skipped
- All prompts and messages are in English

## License

This project is based on [Better-Kemono-and-Coomer-Downloader](https://github.com/isaswa/Better-Kemono-and-Coomer-Downloader) and simplified for Kemono-only downloads.

## Troubleshooting

**Session initialization failed**: The program will continue but may encounter access restrictions. Try running again.

**403 Errors**: The program will automatically retry with exponential backoff. If it persists, wait a few minutes before trying again.

**Invalid URL format**: Ensure URLs follow the correct format:
- Post URL: `https://kemono.cr/service/user/user_id/post/post_id`
- Profile URL: `https://kemono.cr/service/user/user_id`
