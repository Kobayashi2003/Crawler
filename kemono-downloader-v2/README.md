# auto-kemono-downloader

> **⚠️ Deprecated — no longer maintained.**
> Development has moved to **pawchive-downloader**, which reuses the same
> creator/post ids. To migrate your data (artists, download state, config), run
> `python migrate_from_kemono.py` from the pawchive-downloader project.
> See `TODO.archived.md` for the historical backlog.

A downloader for [Kemono](https://kemono.cr). Automates content downloading with artist management, scheduling, and concurrent downloads.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

Enter `help` to see all available commands. Basic workflow:

```bash
> add                  # Add an artist by URL
> list                 # List all artists
> check                # Download updates for an artist
> check-all            # Download updates for all artists
> tasks                # View active downloads
```

### Sort and Filter

```bash
> list:sort_by=name     # Sort by name / status / posts / recent
> check-from            # Download from a specific date
> check-range           # Download within a date range
```
