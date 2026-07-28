import copy
from functools import lru_cache
from os import PathLike
from pathlib import PurePosixPath


class Library:
    __slots__ = [
        '_name', '_root',
        '_group', '_raw_group_parts', '_artifact', '_version',
        '_classifier', '_ok', '_path', '_parent_dir'
    ]

    @lru_cache
    def __new__(cls, name, root=None):
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

    def _generate_parts(self):
        if self._ok: return
        parts = self._name.split(':')
        if len(parts) == 3:
            self._group, self._artifact, self._version = parts

        elif len(parts) == 4:
            self._group, self._artifact, self._version, self._classifier = parts

        else:
            raise ValueError('Invalid library name', self._name)

        self._raw_group_parts = self._group.split('.')
        self._ok = True

    @property
    def name(self):
        return self._name

    @property
    def path(self):
        if self._path:
            return self._path

        self._generate_parts()

        if self._classifier:
            filename = f'{self._artifact}-{self._version}-{self._classifier}.jar'

        else:
            filename = f'{self._artifact}-{self._version}.jar'

        self._path = PurePosixPath(
            *self._raw_group_parts,
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

        self._parent_dir = os.path.join(*self._raw_group_parts, self._artifact, self._version)
        return self._parent_dir

    @property
    def fullpath(self):
        if not self._root:
            raise ValueError('Library root not set')
        return os.path.join(self._root, self.path)

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
        return self.__class__(f'{self._name}:{classifier}', self._root)

    def with_root(self, root):
        obj = copy.copy(self)
        obj._root = root
        return obj
