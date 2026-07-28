import os
import typing
from os import PathLike
from pathlib import Path
from typing import Any

import msgspec

if typing.TYPE_CHECKING:
    from app.core.minecraft.base_models import Downloads


class FileInfo[T=None](msgspec.Struct, kw_only=True):
    filename: str | PathLike[str]
    size: int | None = None
    hash: str | None = None
    algorithm: str = 'sha1'
    key: str = None
    meta: T = None

    def __fspath__(self):
        return os.fspath(self.filename)

    def relative_to(self, path):
        return msgspec.structs.replace(
            self, filename=Path(path) / self.filename
        )

    @classmethod
    def from_downloads_struct(cls, downloads: Downloads, filename, meta: T = None):
        return cls(
            filename=filename,
            size=downloads.size,
            hash=downloads.sha1,
            meta=meta
        )


class ValidateResult[T=None](msgspec.Struct, kw_only=True):
    result: bool
    file: FileInfo[T] | None = None
    size: int | None = None
    hash: str | None = None
    error: Any | None = None

    @property
    def ok(self):
        return self.error is None

    def raise_for_error(self):
        if self.error is not None:
            raise self.error

    def __fspath__(self):
        return self.file.filename
