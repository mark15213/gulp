"""URL helpers shared by capture and the metadata-resolution job."""

from urllib.parse import urlsplit


def host_of(url: str) -> str:
    return urlsplit(url).hostname or url
