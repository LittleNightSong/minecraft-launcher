import os
from pathlib import Path

import msgspec

from app.core.java import detect_java_version
from app.core.java.detector import search_java


class RepositoryRecord(msgspec.Struct):
    name: str
    path: Path


class UserIDRecord(msgspec.Struct):
    name: str  # TODO 补充更多信息
    # type\: Literal['offline'] = "offline"


class JavaRecord(msgspec.Struct, frozen=True):
    type: str
    major: int
    path: str

    @classmethod
    async def from_path(cls, path):
        type, major = await detect_java_version(path)
        if type is None:
            return None

        return cls(
            type, major, path
        )

    @classmethod
    def search(cls, path, max_depth=None):
        return search_java(path, max_depth)

    @classmethod
    def resolved(cls, path, type, major):
        return cls(
            type, major,
            Path(path).resolve(strict=True).__fspath__()
        )

    @classmethod
    def new(cls, path, type, major):
        return cls(type, major, path)

    def resolve(self):
        return self.__class__.resolved(
            self.path, self.type, self.major
        )

    def java_path(self):
        path = self.path
        if os.name == 'nt':
            return os.path.join(path, 'java.exe')
        else:
            return os.path.join(path, 'java')

    def javaw_path(self):
        path = self.path
        if os.name == 'nt':
            return os.path.join(path, 'javaw.exe')
        else:
            return os.path.join(path, 'javaw')

    def __hash__(self) -> int:
        return hash(self.path)

    def __eq__(self, value: object, /) -> bool:
        return hash(self) == hash(value)


class ServerRecord(msgspec.Struct):
    """
    服务器记录类型
    
    :ivar name: （唯一键）服务器名称
    :ivar addr: 服务器地址，结构为 host:port
    :ivar bind: 绑定的实例名称，当需要进入此服务器时将启动它
    """
    name: str
    addr: str
    bind: str

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, __o: object) -> bool:
        return hash(__o) == hash(self.name)
