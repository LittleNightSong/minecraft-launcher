import zipfile
from functools import cached_property, lru_cache

import msgspec

from app.core.addon.pack.pack_meta import PackMeta


class PackFile:
    __slots__ = ('_file', '_metadata', '_fp', '__dict__')
    def __init__(self, fp):
        self._fp = fp
        self._file = zipfile.ZipFile(fp, 'r')
        self._metadata = None

    @property
    def metadata(self) -> PackMeta | None:
        if self._metadata is None:
            try:
                self._metadata = msgspec.json.decode(
                    self._file.read('pack.mcmeta'),
                    type=PackMeta
                )
            except KeyError:
                self._metadata = None

        return self._metadata

    @lru_cache(1)
    def is_vaild(self):
        return 'pack.mcmeta' in self._file.namelist()

    @lru_cache(1)
    def is_resourcepack(self):
        return any(i.startswith('assets/')  for i in self._file.namelist())

    @lru_cache(1)
    def is_datapack(self):
        return any(i.startswith('data/')  for i in self._file.namelist())

    @lru_cache(1)
    def is_shaderpack(self):
        return any(
            i.startswith('shaders/') or i.endswith(('.glsl', '.vsh', '.fsh'))
            for i in self._file.namelist()
        )

    def read_icon(self):
        return self._file.read('pack.png')


