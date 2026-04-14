import re


def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = name.strip(' .')
    return name if name else '_'


def isJableVideoUrl(url):
    if re.match(r'.*jable.tv/videos/.*/', url):
        return True
    else:
        return False


def is_artist_url(url):
    return bool(re.match(r'https?://jable\.tv/models/[^/]+/?$', url))
