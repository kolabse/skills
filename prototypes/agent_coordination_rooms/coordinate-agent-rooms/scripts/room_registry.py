"""On-disk registry for named project rooms."""
from pathlib import Path
import re
from tempfile import TemporaryDirectory

import room
import room_team


ROOM_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
ROOM_URL_PATH = re.compile(rf"/rooms/({ROOM_ID.pattern})/?")
DIRECTORY_PREFIX = "room-"
DB_NAME = "room.sqlite"


class RoomRegistry:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def room_directory(self, name):
        if not ROOM_ID.fullmatch(name):
            raise ValueError("room ID must have 1 to 63 lowercase ASCII letters, digits or hyphens")
        return self.directory / (DIRECTORY_PREFIX + name)

    def lookup(self, name):
        directory = self.room_directory(name)
        path = directory / DB_NAME
        if directory.is_symlink() or path.is_symlink() or not path.is_file():
            raise FileNotFoundError(f"room not found: {name}")
        return path

    def names(self):
        if not self.directory.exists():
            return []
        names = []
        for directory in self.directory.iterdir():
            name = directory.name.removeprefix(DIRECTORY_PREFIX)
            if directory.name == name or not ROOM_ID.fullmatch(name):
                continue
            try:
                self.lookup(name)
            except FileNotFoundError:
                continue
            names.append(name)
        return sorted(names)

    def create(self, name, args):
        destination = self.room_directory(name)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError(f"room already exists: {name}")
        # Publish only a fully initialized database. A concurrent creator cannot
        # replace the winning non-empty directory.
        with TemporaryDirectory(prefix=".creating-", dir=self.directory) as temporary:
            staged = Path(temporary) / "ready"
            staged.mkdir(mode=0o700)
            with room.transaction(staged / DB_NAME, True, initialize=True) as db:
                room.init(db, args)
                room.install_tokens(db)
                room_team.install(db)
            try:
                staged.rename(destination)
            except OSError as error:
                if destination.exists():
                    raise ValueError(f"room already exists: {name}") from error
                raise
        return {"room": name}
