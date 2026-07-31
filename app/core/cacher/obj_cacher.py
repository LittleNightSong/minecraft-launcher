import time

import msgspec

_UNSET = object()


class ObjCacher:
    UNSET = _UNSET
    def __init__(self):
        self.cache = {}

    def set(self, key: str, value, ttl=-1):
        self.cache[key] = {
            'value': value,
            'ttl': ttl,
            'timestamp': time.time()
        }

    def get(self, key: str):
        if key in self.cache:
            entity = self.cache[key]
            if entity['ttl'] < 0:  # 永久有效
                return entity['value']
            elif time.time() - entity['timestamp'] < entity['ttl']:  # 仍然有效
                return entity['value']
            else:
                del self.cache[key]  # 已经失效,自动清理
                return _UNSET
        else:
            return _UNSET

    def remove(self, key: str):
        if key in self.cache:
            del self.cache[key]

    def export(self, filename: str):
        with open(filename, 'wb') as f:
            f.write(msgspec.msgpack.encode(self.cache))

    @classmethod
    def load(cls, filename: str):
        with open(filename, 'rb') as f:
            self = cls()
            self.cache = msgspec.msgpack.decode(f.read())
            return self
