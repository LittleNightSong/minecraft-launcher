# file.py
# Doc by DeepSeek
import dataclasses
from os import PathLike
from typing import Any

import msgspec


class FileSpec[T](msgspec.Struct, kw_only=True, frozen=True, gc=False):
    """
    文件信息类，用于描述一个文件的基本元数据。

    包含文件名、大小、哈希值等信息，支持泛型用于附加元数据。

    :param filename: 文件名或路径
    :param size: 文件大小（字节），默认为 None
    :param checksum: 文件哈希值，默认为 None
    :param algorithm: 哈希算法，默认为 'sha1'
    :param key: 文件键名，默认为 None
    :param meta: 附加元数据，默认为 None
    """
    size: int | None = None
    checksum: str | None = None
    algorithm: str = 'sha1'
    last_modified: float | int | None = None
    meta: T | None = None

    def replace(self, **kwargs):
        return dataclasses.replace(self, **kwargs)


class ValidateResult[T](msgspec.Struct, kw_only=True, frozen=True, gc=False):
    """
    文件验证结果类。

    用于表示文件验证操作的结果，包含验证状态、文件信息、错误信息等。

    :param result: 验证是否通过
    :param file: 被验证的文件信息，默认为 None
    :param size: 实际文件大小，默认为 None
    :param checksum: 实际文件哈希值，默认为 None
    :param error: 验证过程中的错误，默认为 None
    """
    result: bool
    file: str | PathLike[str]
    spec: FileSpec[T]
    size: int | None = None
    checksum: str | None = None
    last_modified: float | int | None = None
    error: BaseException | None = None

    @property
    def success(self):
        """检查验证是否成功（无错误）。"""
        return self.error is None

    @property
    def ok(self):
        return self.result

    def raise_for_error(self):
        """
        如果存在错误则抛出异常。

        :raises: 验证过程中存储的错误
        """
        if self.error is not None:
            raise self.error

    def exists(self) -> bool:
        return self.size is not None

    def __fspath__(self):
        """返回被验证文件的路径，支持 os.fspath() 操作。"""
        return self.file
