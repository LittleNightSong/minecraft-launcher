import base64
import builtins
import hashlib
import time
from collections.abc import Buffer
from pathlib import Path

import msgspec
import xxhash
from loguru import logger

from app.core.common import write_model, read_model
from app.core.osio import safe_unlink, safe_mkdir


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

    def set_ttl(self, ttl: int | float):
        self.meta.ttl = ttl
        logger.debug("设置 {xkey} 的 ttl={ttl}", xkey=self.xkey, ttl=ttl)
        return self

    def set_last_modified(self, last_modified: int | float):
        logger.debug("设置 {xkey} 的 last_modified={last_modified}", xkey=self.xkey, last_modified=last_modified)
        self.meta.last_modified = last_modified
        return self

    def set_data(self, data: Buffer):
        logger.debug("设置了 {xkey} 的 raw data", xkey=self.xkey)
        with open(self.data_file, 'wb') as f:
            f.write(data)

    @property
    def files(self):
        return self.meta_file, self.data_file

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
        safe_unlink(self.meta_file)
        safe_unlink(self.data_file)
        return self

    def sync_metadata(self):
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


class CacheManager:
    def __init__(self, root, xkey_algorithm='xxhash', disabled: bool = False):
        self.path = Path(root)
        self.xkey_algorithm = xkey_algorithm
        self.disabled = disabled

    def entity(self, key, suffix: str):
        xkey = compute_xkey(key, self.xkey_algorithm)
        logger.debug("获取缓存体 {xkey}", xkey=xkey)
        return CacheEntity(self, key, xkey, suffix)

    def cache_files(self, key: str, type_suffix: str):
        return self.entity(key, type_suffix).files

    def set_model(self, key, value: msgspec.Struct, ttl=-1):
        if self.disabled:
            return None

        with self.entity(key, suffix='model') as entity:
            entity.set_ttl(ttl).set_last_modified(time.time()).set_data(
                msgspec.msgpack.encode(value)
            )
        return value

    def get_model[T](self, key, type: builtins.type[T]) -> T:
        if self.disabled:
            return None

        with self.entity(key, suffix='model') as entity:
            if entity.auto_cleanup():
                return None
            else:
                return read_model(entity.data_file, type, decoder=msgspec.msgpack.decode)

    def ensure_exists(self):
        self.path.mkdir(parents=True, exist_ok=True)
