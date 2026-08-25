import shutil
from contextlib import contextmanager
from os import PathLike
from pathlib import Path

from app.core.osio import safe_unlink


class FileCacher:
    def __init__(self, cache_dir: str | PathLike[str]):
        self.path = Path(cache_dir)
        self.processing_files = set()
        self.processing_dirs = set()

    def is_in_processing(self, filename):
        return filename in self.processing_files and all(not filename.startswith(i) for i in self.processing_dirs)

    @contextmanager
    def open(self, filename, /, cleanup_on_error=True):
        if self.is_in_processing(filename):
            raise RuntimeError(f"File '{filename}' is already cached")

        self.processing_files.add(filename)
        try:
            yield Path(self.path / filename)
        except BaseException:
            if cleanup_on_error:
                safe_unlink(self.path / filename)
            raise
        finally:
            self.processing_files.remove(filename)

    @contextmanager
    def use(self, dir, /, cleanup_on_error=True):
        if self.is_in_processing(dir):
            raise RuntimeError(f"Directory '{dir}' is already cached")
        self.processing_dirs.add(dir)
        try:
            yield Path(self.path / dir)
        except BaseException:
            if cleanup_on_error:
                shutil.rmtree(self.path / dir, ignore_errors=True)
            raise
        finally:
            self.processing_dirs.remove(dir)


    def exists(self, filename):
        return (self.path / filename).is_file()

    def ensure_exists(self):
        self.path.mkdir(parents=True, exist_ok=True)