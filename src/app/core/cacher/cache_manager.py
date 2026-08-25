import base64
import hashlib
import time
from collections.abc import Buffer
from contextlib import contextmanager
from pathlib import Path

import msgspec
import xxhash
from loguru import logger

from app.core.common import write_model
from app.core.osio import safe_mkdir, safe_unlink


class CacheManager:
    def __init__(self, root, xkey_algorithm='xxhash'):
        self.path = Path(root)
        self.xkey_algorithm = xkey_algorithm
        self.in_process = set()

    @contextmanager
    def entity(self, key, suffix: str):
        xkey = compute_xkey(key, self.xkey_algorithm)
        if xkey in self.in_process:
            logger.warning("尝试访问了使用中的缓存：{} ({})", key, xkey)
            raise RuntimeError("该缓存正在使用中")

        self.in_process.add(xkey)
        logger.debug("获取缓存体 {xkey} ({key})", xkey=xkey, key=key)
        try:
            with CacheEntity(self, key, xkey, suffix) as entity:
                yield entity
        finally:
            self.in_process.remove(xkey)

    def cache_files(self, key: str, type_suffix: str):
        with self.entity(key, type_suffix) as e:
            return e.files

    def ensure_exists(self):
        self.path.mkdir(parents=True, exist_ok=True)

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

    @classmethod
    def safe_from_file(cls, filename, default=...):
        try:
            return cls.from_file(filename)
        except FileNotFoundError:
            if default is not ...:
                return default
            else:
                return CacheFileMetadata()

    def save_to_file(self, filename):
        with open(filename, 'wb') as f:
            f.write(msgspec.msgpack.encode(self))



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

        self.meta_file = self.cacher.path / xkey[:2] / f"{xkey}.{type_suffix}-m"
        self.data_file = self.cacher.path / xkey[:2] / f"{xkey}.{type_suffix}-d"

        self.meta = CacheFileMetadata.safe_from_file(self.meta_file)

        self._closed = False

    @property
    def is_closed(self):
        return self._closed

    def check_closed(self):
        if self._closed:
            raise IOError("Cannot operate on a closed entity")

    def set_ttl(self, ttl: int | float):
        self.check_closed()
        self.meta.ttl = ttl
        logger.debug("设置 {xkey} 的 ttl={ttl}", xkey=self.xkey, ttl=ttl)
        return self

    def set_last_modified(self, last_modified: int | float):
        self.check_closed()
        logger.debug("设置 {xkey} 的 last_modified={last_modified}", xkey=self.xkey, last_modified=last_modified)
        self.meta.last_modified = last_modified
        return self

    def write_data(self, data: Buffer):
        self.check_closed()
        logger.debug("设置了 {xkey} 的 raw data", xkey=self.xkey)
        with open(self.data_file, 'wb') as f:
            f.write(data)

    @property
    def files(self):
        return self.meta_file, self.data_file

    def is_stale(self) -> bool:
        return not self.exists() or self.meta.is_stale()

    def exists(self):
        return self.meta_file.exists()

    def auto_cleanup(self):
        self.check_closed()
        if self.meta.is_stale():
            self.cleanup()
            return True

        return False

    def ensure_directory(self):
        self.check_closed()
        safe_mkdir(self.cacher.path / self.xkey[:2])
        return self

    def cleanup(self):
        self.check_closed()
        safe_unlink(self.meta_file)
        safe_unlink(self.data_file)
        return self

    def sync_metadata(self):
        self.check_closed()
        self.ensure_directory()
        write_model(
            file=self.meta_file,
            obj=self.meta,
            encoder=msgspec.msgpack.encode
        )
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sync_metadata()
        self._closed = True


def compute_xkey(key: str, algorithm: str):
    if algorithm == 'xxhash':
        return base64.urlsafe_b64encode(xxhash.xxh3_128(key.encode()).digest()).decode()
    else:
        return base64.urlsafe_b64encode(hashlib.new(algorithm, key.encode()).digest()).decode()
