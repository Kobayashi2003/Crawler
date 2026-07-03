# TODO (Archived)

> **Archived — kemono-downloader-v2 is no longer maintained.**
> Development has moved to `pawchive-downloader`. The items below are kept for
> historical reference only and will not be worked on here.

## Bugs

- Files downloaded through the browser proxy end up with incorrect file paths.
- The posts response should be de-duplicated before caching: for reasons unknown,
  the official API sometimes returns duplicate post ids.
  *(Later addressed in `downloader.update_posts_basic`, which de-dupes by id.)*

## Under discussion

- `last_date` in `artist.json` is currently updated once a whole
  `download_artist` task finishes. Consider updating it after each
  `download_post` instead, so that if an artist has many pending posts and the
  task is interrupted, restarting doesn't re-scan a large number of
  already-downloaded posts. The downside is more frequent file writes plus the
  synchronization concerns that introduces.

- Duplicate-download detection currently lives in `api.download_file`: it first
  obtains the `content-length` header via a streaming request and then checks
  whether the file already exists, skipping the download if so. This works but
  costs an extra HTTP request. Consider adding a `content-length` cache — store
  it on first download and reuse it from the downloader on later runs to decide
  whether a file already exists, avoiding the extra request.
