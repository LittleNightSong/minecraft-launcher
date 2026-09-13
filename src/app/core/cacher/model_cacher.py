import builtins
import time

import msgspec
from loguru import logger

from app.core.cacher.cache_manager import CacheManager
from app.core.common import read_model
from app.core.pprofile import chronomia


class ModelCacher(CacheManager):
    def __init__(self, root, xkey_algorithm='xxhash'):
        super().__init__(root, xkey_algorithm)
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
        if ttl is None:
            ttl = self.get_default_ttl(key) or -1

        logger.debug("写入缓存 {} (TTL {})", key, ttl)

        with self.entity(key, suffix='model') as e:
            (
                e
                .set_ttl(ttl)
                .set_last_modified(time.time())
                .write_data(msgspec.msgpack.encode(value))
            )
        return value

    @chronomia.cell(name='model-cacher.get')
    def get[T](self, key, type: builtins.type[T], allow_stale=False) -> T | None:
        with self.entity(key, suffix='model') as entity:
            if not allow_stale:  # 如果不允许返回过期的数据
                if entity.auto_cleanup():  # 尝试自动清理，清理成功返回 True
                    logger.debug("正在访问的缓存 {!r} 已过期（自动清理）", key)
                    return None  # 已过期，返回 None
                else:  # 没过期，正常读取数据文件
                    logger.debug("正在访问的缓存 {!r} 未过期（已返回）", key)
                    return read_model(entity.data_file, type, decoder=msgspec.msgpack.decode)
            else:  # 允许过期，那么直接返回，不做处理
                logger.debug("正在访问的缓存 {!r} 未检查（已返回）", key)
                return read_model(entity.data_file, type, decoder=msgspec.msgpack.decode)
