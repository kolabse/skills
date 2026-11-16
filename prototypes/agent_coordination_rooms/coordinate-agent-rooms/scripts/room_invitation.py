"""Versioned invitation links shared by the operator and the client."""
import re

import room_client
from room_registry import ROOM_URL_PATH


VERSION = 1
REVISION = re.compile(r"[0-9a-f]{40}")
SECRET = re.compile(r"[A-Za-z0-9_-]{43}")
SOURCE = "https://github.com/kolabse/skills/tree/{revision}/prototypes/agent_coordination_rooms/coordinate-agent-rooms"


def parse_link(link):
    if not isinstance(link, str) or not link.endswith("/invite") or any(char.isspace() for char in link):
        raise ValueError("expected an AICQ room invitation link")
    room_url = link.removesuffix("/invite")
    url = room_client.validate_url(room_url)
    match = ROOM_URL_PATH.fullmatch(url.path)
    if match is None or url.path.endswith("/"):
        raise ValueError("expected an AICQ room invitation link")
    return room_url, match.group(1)


def split_invitation(link):
    manifest, marker, token = link.partition("#")
    parse_link(manifest)
    if marker and not SECRET.fullmatch(token):
        raise ValueError("invalid AICQ invitation fragment")
    return manifest, token if marker else None
