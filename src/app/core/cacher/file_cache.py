from contextlib import contextmanager
from os import PathLike
from pathlib import Path


class FileCacher:
    def __init__(self, cache_dir: str | PathLike[str]):
        self.path = Path(cache_dir)
        self.in_process = set()

    @contextmanager
    def open(self, filename):
        self.in_process.add(filename)
        try:
            yield Path(self.path / filename)
        finally:
            self.in_process.remove(filename)

    def exists(self, filename):
        return (self.path / filename).is_file()

    def ensure_exists(self):
        self.path.mkdir(parents=True, exist_ok=True)