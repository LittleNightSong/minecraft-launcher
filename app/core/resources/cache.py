import base64
import builtins
import hashlib
import os.path
import time
from collections.abc import Buffer
from pathlib import Path

import msgspec
import xxhash

from app.core.common import write_model, read_model
from app.core.resources.base import BaseDirectory


def safe_unlink(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def safe_mkdir(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        pass


def compute_xkey(key: str, algorithm: str):
    if algorithm == 'xxhash':
        return base64.urlsafe_b64encode(xxhash.xxh3_128(key).digest()).decode()
    else:
        return base64.urlsafe_b64encode(hashlib.new(algorithm, key.encode()).digest()).decode()


class CacheFileMetadata(msgspec.Struct):
    last_modified: int | float = -1  # Timestamp in seconds
    ttl: int | float = -1  # Max-age in seconds

    # extra: dict = msgspec.field(default_factory=dict)  # Extra values

    def is_stale(self) -> bool:
        if self.last_modified == -1:
            return True

        if self.ttl == -1:
            return False

        return (time.time() - self.last_modified) > self.ttl

    @classmethod
    def from_file(cls, filename):
        with open(filename, 'rb') as f:
            return msgspec.msgpack.decode(f.read(), type=cls)

    def save_to_file(self, filename):
        with open(filename, 'wb') as f:
            f.write(msgspec.msgpack.encode(self))


# @disjoint_base
# class BaseCacheType:
#     def __cache_dump__(self) -> Iterable[Buffer]:
#         ...
#
#     @classmethod
#     def __cache_load__(cls, stream):
#         ...


class CacheEntity:
    def __init__(
            self,
            cacher: CacheManager,
            key: str, xkey: str,
            type_suffix: str
    ):
        self.cacher = cacher
        self.key = key
        self.xkey = xkey

        self.file_meta = self.cacher.path / xkey[:2] / f"{xkey}.{type_suffix}.meta"
        self.file_data = self.cacher.path / xkey[:2] / f"{xkey}.{type_suffix}.data"

        self.meta = CacheFileMetadata.from_file(self.file_meta)

    def set_ttl(self, ttl: int | float):
        self.meta.ttl = ttl
        return self

    def set_last_modified(self, last_modified: int | float):
        self.meta.last_modified = last_modified
        return self

    def set_data(self, data: Buffer):
        with open(self.file_data, 'wb') as f:
            f.write(data)

    @property
    def files(self):
        return self.file_meta, self.file_data

    def is_stale(self) -> bool:
        return self.meta.is_stale()

    def auto_cleanup(self):
        if self.meta.is_stale():
            self.cleanup()
            return True

        return False

    def ensure_directory(self):
        safe_mkdir(self.cacher.path / self.xkey[:2])
        return self

    def cleanup(self):
        safe_unlink(self.file_meta)
        safe_unlink(self.file_data)
        return self

    def sync_metadata(self):
        write_model(
            file=self.file_meta,
            obj=self.meta,
            encoder=msgspec.msgpack.encode
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sync_metadata()


class CacheManager(BaseDirectory):
    def __init__(self, root, xkey_algorithm='xxhash'):
        self.path = Path(root)
        self.xkey_algorithm = xkey_algorithm

    def entity(self, key, suffix: str):
        xkey = compute_xkey(key, self.xkey_algorithm)
        return CacheEntity(self, key, xkey, suffix)

    def cache_files(self, key: str, type_suffix: str):
        return self.entity(key, type_suffix).files

    def set(self, key, value: msgspec.Struct, ttl=-1):
        self.entity(key, suffix='model').set_ttl(ttl).set_last_modified(time.time())
        return value

    def get[T: 'msgspec.Struct'](self, key, type: builtins.type[T]) -> T:
        with self.entity(key, suffix='model') as entity:
            if entity.auto_cleanup():
                return None
            else:
                return read_model(entity.file_data, type)
