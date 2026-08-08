import builtins
import time

import msgspec

from app.core.cacher.cache_manager import CacheManager
from app.core.common import read_model


class ModelCacher(CacheManager):
    def __init__(self, root, xkey_algorithm='xxhash', disabled: bool = False):
        super().__init__(root, xkey_algorithm, disabled)
        self._default_ttl = {}

    @staticmethod
    def split_key(key):
        return tuple(str(key).split(':', 1))

    def set_default_ttl(self, namespace, tll: int = -1):
        self._default_ttl[namespace] = tll
        return self

    def get_default_ttl(self, key):
        return self._default_ttl.get(self.split_key(key)[0])

    def set(self, key, value: msgspec.Struct, ttl: int | None = None):
        if self.disabled:
            return None

        if ttl is None:
            ttl = self.get_default_ttl(key) or -1

        with self.entity(key, suffix='model') as e:
            (
                e
                .set_ttl(ttl)
                .set_last_modified(time.time())
                .write_data(msgspec.msgpack.encode(value))
            )
        return value

    def get[T](self, key, type: builtins.type[T], allow_stale=False) -> T | None:
        if self.disabled:
            return None

        with self.entity(key, suffix='model') as entity:
            if not allow_stale:
                if entity.auto_cleanup():
                    return None
                else:
                    return read_model(entity.data_file, type, decoder=msgspec.msgpack.decode)
            else:
                return read_model(entity.data_file, type, decoder=msgspec.msgpack.decode)

