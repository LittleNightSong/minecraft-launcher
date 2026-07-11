import copy
import os.path
from os import PathLike
from pathlib import Path

from app.core.resources.base import BaseDirectory


class Library:
    __slots__ = [
        'name', 'root',
        '_group', '_group_parts_o', '_artifact', '_version',
        '_classifier', '_ok', '_path', '_parent_dir'
    ]

    def __init__(self, name: str, root: PathLike[str] | None = None):
        self.name: str = name
        self.root: PathLike[str] | None = root

        self._group: str = None
        self._group_parts_o: list[str] = None
        self._artifact: str = None
        self._version: str = None
        self._classifier: str = None
        self._ok: bool = False
        self._path: str = None
        self._parent_dir: str = None

    @property
    def _group_parts(self):
        self._generate_parts()
        if self._group_parts_o is None:
            self._group_parts_o = self._group.split('.')

        return self._group_parts_o

    def _generate_parts(self):
        if self._ok: return
        parts = self.name.split(':')
        if len(parts) == 3:
            self._group, self._artifact, self._version = parts

        elif len(parts) == 4:
            self._group, self._artifact, self._version, self._classifier = parts

        else:
            raise ValueError('Invalid library name', self.name)

        self._ok = True

    @property
    def path(self):
        if self._path:
            return self._path

        self._generate_parts()

        if self._classifier:
            filename = f'{self._artifact}-{self._version}-{self._classifier}.jar'

        else:
            filename = f'{self._artifact}-{self._version}.jar'

        self._path = os.path.join(
            *self._group_parts,
            self._artifact,
            self._version,
            filename
        )
        return self._path

    @property
    def parent_dir(self):
        if self._parent_dir:
            return self._parent_dir

        self._generate_parts()

        self._parent_dir = os.path.join(*self._group_parts, self._artifact, self._version)
        return self._parent_dir

    @property
    def fullpath(self):
        if not self.root:
            raise ValueError('Library root not set')
        return os.path.join(self.root, self.path)

    def __fspath__(self):
        return self.fullpath

    @property
    def classifier(self):
        self._generate_parts()
        return self._classifier

    @property
    def group(self):
        self._generate_parts()
        return self._group

    @property
    def artifact(self):
        self._generate_parts()
        return self._artifact

    @property
    def version(self):
        self._generate_parts()
        return self._version

    def with_classifier(self, classifier):
        return self.__class__(f'{self.name}:{classifier}', self.root)

    def with_root(self, root):
        obj = copy.copy(self)
        obj.root = root
        return obj


class LibrariesDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

    def library(self, name: str):
        return Library(name, self.path)

    # @trace
    async def check(self, name, hash, size=None):
        return self.library(name).check(hash, size)
