import asyncio
import dataclasses
import os
from asyncio import as_completed
from os import PathLike
from typing import Iterable, Any, AsyncGenerator

from app.core.common import thread_executor
from app.core.minecraft.base_models import Downloads

default_chunk_size = 1024 * 1024


@dataclasses.dataclass(kw_only=True, slots=True)
class FileInfo[T=None]:
    filename: str | PathLike[str]
    size: int | None = None
    hash: str | None = None
    algorithm: str = 'sha1'
    key: str = None
    meta: T = None

    def __fspath__(self):
        return os.fspath(self.filename)

    @classmethod
    def new(cls, filename, size: int | None, hash: str | None, meta: T = None) -> FileInfo[T]:
        return cls(
            filename=filename, size=size, hash=hash, meta=meta
        )

    @classmethod
    def from_downloads_struct(cls, downloads: Downloads, filename, meta: T = None):
        return cls(
            filename=filename,
            size=downloads.size,
            hash=downloads.sha1,
            meta=meta
        )


@dataclasses.dataclass(kw_only=True, slots=True)
class ValidateResult[T=None]:
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


def _compute_hash(file, algorithm='sha1', chunk_size=default_chunk_size):
    import hashlib
    hasher = hashlib.new(algorithm)

    fd = os.open(file, os.O_RDONLY | os.O_BINARY)

    buffer = bytearray()
    buffer.resize(chunk_size)

    try:

        while n := os.readinto(fd, buffer):
            hasher.update(buffer[:n])

    finally:
        os.close(fd)
        buffer.clear()
        del buffer

    return hasher.hexdigest()


async def compute_hash(
        file, algorithm='sha1', chunk_size=default_chunk_size,
):
    return await asyncio.to_thread(
        _compute_hash,
        file, algorithm, chunk_size
    )


def _validate[T](file: FileInfo[T], chunk_size: int = default_chunk_size) -> ValidateResult[T]:
    real_size = None
    real_hash = None

    try:
        # 最先确保文件的存在性
        filename = file.filename
        if not os.path.exists(filename):
            return ValidateResult(
                result=False,
                file=file,
            )

        # 再检查 fileszie
        filesize = file.size
        if filesize is not None and filesize != (real_size := os.stat(filename).st_size):
            return ValidateResult(
                result=False,
                file=file,
                size=real_size
            )

        # 其次检查 hash
        hash = file.hash
        algorithm = file.algorithm

        if (
                hash is not None and
                (
                        real_hash := _compute_hash(
                            filename,
                            algorithm=algorithm,
                            chunk_size=chunk_size
                        )
                ) != hash
        ):
            return ValidateResult(
                result=False,
                file=file,
                size=real_size,
                hash=real_hash
            )

        return ValidateResult(
            result=True,
            file=file,
            size=filesize,
            hash=real_hash
        )
    except Exception as e:  # 发生任何异常都应该返回一个带错误信息的 Result 类型
        return ValidateResult(
            result=False,
            file=file,
            size=real_size,
            hash=real_hash,
            error=e
        )


class FileValidator:
    def __init__(self, executor=None, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.executor = executor or thread_executor

    async def validate[T](self, file: FileInfo[T], chunk_size: int = default_chunk_size) -> ValidateResult[T]:
        return await self.loop.run_in_executor(self.executor, _validate, file, chunk_size)


def res_false_filter[T](results: Iterable[ValidateResult[T]]) -> list[ValidateResult[T]]:
    return [r for r in results if not r.result]


def res_true_filter[T](results: Iterable[ValidateResult[T]]) -> list[ValidateResult[T]]:
    return [r for r in results if r.result]

