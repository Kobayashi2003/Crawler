import re


def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = name.strip(' .')
    return name if name else '_'


def is_video_url(url):
    return bool(re.match(r'https?://jable\.tv/videos/[^/]+/?$', url))


def is_artist_url(url):
    return bool(re.match(r'https?://jable\.tv/models/[^/]+/?$', url))


def extract_video_id(url):
    return url.rstrip('/').split('/')[-1]
