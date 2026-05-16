import hashlib
import time
from pathlib import Path

import xxhash

from app.common.methods import read_json, write_json
from app.resources.base import BaseDirectory


class CacheFile:
    __slots__ = ('cache_dir', 'key', 'metadata')

    def __init__(self, cache_dir: CacheDirectory, key: str):
        self.cache_dir = cache_dir
        self.key = key
        self.metadata = None

    @property
    def file(self):
        return self.cache_dir.path / self.key

    @property
    def metafile(self):
        return self.cache_dir.path / (self.key + '.meta')

    @property
    def timestamp(self):
        return self.metadata.get('timestamp')

    @timestamp.setter
    def timestamp(self, value):
        self.metadata['timestamp'] = value

    @property
    def max_age(self):
        return self.metadata.get('max-age', -1)

    @max_age.setter
    def max_age(self, value):
        self.metadata['max-age'] = value

    @property
    def size(self):
        return self.file.stat().st_size

    @property
    def refcount(self):
        return self.file.stat().st_nlink

    def load(self):
        try:
            self.metadata = read_json(self.metafile)
        except FileNotFoundError:
            self.metadata = {}

    def save(self):
        write_json(self.metafile, self.metadata)

    def is_valid(self, t=None):
        if not self.metadata or "timestamp" not in self.metadata:
            return False

        if self.max_age < 0:
            return True
        elif self.max_age == 0:
            return False
        else:
            t = t or time.time()
            return self.timestamp + self.max_age > t

    def autoclean(self):
        if not self.is_valid() and self.refcount == 1:
            self.file.unlink(missing_ok=True)
            self.metafile.unlink(missing_ok=True)
            return True
        return False

    def linkto(self, target, force=False):
        target = Path(target)
        if target.exists() and force:
                target.unlink()

        target.hardlink_to(self)

    def set(self, file=None, mode='copy'):
        if file is None:
            self.metadata['timestamp'] = time.time()
            return

        file = Path(file)

        if file == self.file:
            pass

        elif mode == 'copy':
            file.copy(self.file)

        elif mode == 'hardlink':
            file.hardlink_to(self.file)

        elif mode == 'symlink':
            file.symlink_to(self.file)

        else:
            raise ValueError(mode)

        self.metadata['timestamp'] = time.time()

    def read_json(self):
        return read_json(self.file)

    def __fspath__(self):
        return str(self.file)

    def __enter__(self):
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()


class CacheDirectory(BaseDirectory):
    def __init__(self, root, hash_algorithm='xxhash'):
        self.path = Path(root)
        self.hash_algorithm = hash_algorithm

    def compute_hash(self, key):
        if self.hash_algorithm == 'xxhash':
            return xxhash.xxh3_128_hexdigest(key)
        else:
            return hashlib.new(self.hash_algorithm, str(key).encode()).hexdigest()

    def get(self, key):
        cache_key = self.compute_hash(key)
        metafile = self.path / (cache_key + '.meta')
        if not metafile.exists():
            write_json(metafile, {})

        return CacheFile(self, cache_key)

    def clean(self):
        for metafile in self.path.glob('*.meta'):
            with CacheFile(self, metafile.stem) as file:
                file.autoclean()
