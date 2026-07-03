"""Optional path-formatting plugin (hot-reloaded on every use).

Each hook receives the formatter's inner function and returns a wrapper around
it, so you can massage the inputs before the default logic runs (or bypass it
entirely). All three hooks are no-ops by default; edit and save — no restart
needed. Delete this file to disable plugins completely.

Signatures the inner functions expect:
    artist_folder(artist, template)            -> pathlib.Path
    post_folder(post, template, date_format)   -> str
    format_file(name, idx, template)           -> str
"""


def format_artist_plugin(inner):
    """Wrap artist-folder formatting. `artist` is a src.models.Artist."""
    def wrapper(artist, template):
        return inner(artist, template)
    return wrapper


def format_post_plugin(inner):
    """Wrap post-folder formatting. `post` is a src.models.Post.

    Example (commented): for one patreon creator, cut the title at the first '/'
    so overly long combined titles don't create nested folders.

        if post.service == "patreon" and post.user == "99342295" and "/" in post.title:
            post.title = post.title.split("/", 1)[0].strip()
    """
    def wrapper(post, template, date_format):
        return inner(post, template, date_format)
    return wrapper


def format_file_plugin(inner):
    """Wrap single-file naming.

    Example (commented): cap very long original names at 40 chars, keeping ext.

        stem, dot, ext = name.rpartition('.')
        if dot and len(stem) > 40:
            name = stem[:40] + dot + ext
    """
    def wrapper(name, idx, template):
        return inner(name, idx, template)
    return wrapper
