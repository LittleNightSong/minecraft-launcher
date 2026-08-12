import os
from pathlib import Path


class BaseDirectory:
    path: Path

    __slots__ = ['path']

    def ensure_exists(self):
        self.path.mkdir(parents=True, exist_ok=True)
        return self

    def __fspath__(self):
        return os.fspath(self.path)

    def __truediv__(self, other) -> Path:
        return self.path / other

    def __repr__(self):
        return f'{self.__class__.__name__}({self.path!r})'
