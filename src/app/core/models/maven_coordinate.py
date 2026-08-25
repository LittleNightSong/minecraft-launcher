# library.py
# Doc by DeepSeek
import copy
import os
from functools import lru_cache
from os import PathLike
from pathlib import PurePosixPath


class MavenCoordinate:
    """
    Minecraft 库文件类。

    表示一个 Maven 格式的库文件，支持解析 Maven 坐标、生成文件路径、
    替换分类器等操作。该类使用 __new__ 实现缓存，相同名称的库只创建一个实例。

    :param name: Maven 坐标，格式为 "group:artifact:version" 或 "group:artifact:version:classifier"
    :param root: 库文件根目录，默认为 None
    """
    __slots__ = [
        '_name', '_root',
        '_group', '_raw_group_parts', '_artifact', '_version', '_ext',
        '_classifier', '_ok', '_path', '_parent_dir', '_deduplication_key'
    ]

    @lru_cache
    def __new__(cls, name, root=None):
        """
        创建库实例，使用 LRU 缓存避免重复创建相同名称的库。

        :param name: Maven 坐标
        :param root: 根目录
        :return: Library 实例
        """
        return super().__new__(cls)

    def __init__(self, name: str, root: PathLike[str] | None = None):
        self._name: str = name
        self._root: PathLike[str] | None = root

        self._group: str = None
        self._raw_group_parts: list[str] = None
        self._artifact: str = None
        self._version: str = None
        self._classifier: str = None
        self._ok: bool = False
        self._path: PurePosixPath = None
        self._parent_dir: str = None
        self._ext = '.jar'
        self._deduplication_key = None

    def _generate_parts(self):
        """
        解析 Maven 坐标，提取 group、artifact、version 和 classifier。

        :raises ValueError: 当坐标格式无效时抛出
        """
        if self._ok:
            return

        parts = self._name.split(':')

        res = parts[-1].split('@', 1)
        if len(res) > 1:
            self._ext = '.' + res[1]
            parts[-1] = res[0]

        if len(parts) == 3:
            self._group, self._artifact, self._version = parts

        elif len(parts) == 4:
            self._group, self._artifact, self._version, self._classifier = parts

        else:
            raise ValueError('Invalid library name', self._name)

        self._raw_group_parts = self._group.split('.')
        self._ok = True

    @property
    def deduplication_key(self):
        if self._deduplication_key is None:
            self._deduplication_key = f'{self.group}:{self.artifact}-{self.classifier}'

        # print(self.name, self._deduplication_key)
        return self._deduplication_key

    @property
    def name(self):
        """返回 Maven 坐标名称。"""
        return self._name

    @property
    def path(self):
        """
        返回库文件在仓库中的相对路径。

        :return: PurePosixPath 对象，表示相对于仓库根目录的路径
        """
        if self._path:
            return self._path

        self._generate_parts()

        if self._classifier:
            filename = f'{self._artifact}-{self._version}-{self._classifier}{self._ext}'

        else:
            filename = f'{self._artifact}-{self._version}{self._ext}'

        self._path = PurePosixPath(
            *self._raw_group_parts,
            self._artifact,
            self._version,
            filename
        )
        return self._path

    @property
    def parent_dir(self):
        """
        返回库文件所在目录的相对路径。

        :return: 父目录路径字符串
        """
        if self._parent_dir:
            return self._parent_dir

        self._generate_parts()

        self._parent_dir = os.path.join(*self._raw_group_parts, self._artifact, self._version)
        return self._parent_dir

    @property
    def fullpath(self):
        """
        返回库文件的完整路径（包含根目录）。

        :return: 完整文件路径
        :raises ValueError: 当根目录未设置时抛出
        """
        if not self._root:
            raise ValueError('Library root not set')
        return os.path.join(self._root, self.path)

    def __fspath__(self):
        """返回完整路径，支持 os.fspath() 操作。"""
        return self.fullpath

    @property
    def classifier(self):
        """返回库文件的分类器（如 'natives-windows'）。"""
        self._generate_parts()
        return self._classifier

    @property
    def group(self):
        """返回库文件的 group ID。"""
        self._generate_parts()
        return self._group

    @property
    def artifact(self):
        """返回库文件的 artifact ID。"""
        self._generate_parts()
        return self._artifact

    @property
    def version(self):
        """返回库文件的版本号。"""
        self._generate_parts()
        return self._version

    def with_classifier(self, classifier):
        """
        创建一个带有指定分类器的库副本。

        :param classifier: 分类器名称（如 'natives-windows'）
        :return: 新的 Library 实例
        """
        return self.__class__(f'{self._name}:{classifier}', self._root)

    def with_root(self, root):
        """
        创建一个带有指定根目录的库副本。

        :param root: 新的根目录路径
        :return: Library 实例（可能是副本）
        """
        obj = copy.copy(self)
        obj._root = root
        return obj