"""Optional path-formatting plugin, hot-reloaded on every use.

Each hook receives the formatter's inner function and returns a wrapper, so you
can massage inputs before the default logic runs. All three are no-ops; edit and
save, no restart. Delete this file to disable plugins.

    artist_folder(artist, template)          -> pathlib.Path
    post_folder(post, template, date_format) -> str
    format_file(name, idx, template)         -> str
"""


def format_artist_plugin(inner):
    def wrapper(artist, template):
        return inner(artist, template)
    return wrapper


def format_post_plugin(inner):
    def wrapper(post, template, date_format):
        return inner(post, template, date_format)
    return wrapper


def format_file_plugin(inner):
    def wrapper(name, idx, template):
        return inner(name, idx, template)
    return wrapper
