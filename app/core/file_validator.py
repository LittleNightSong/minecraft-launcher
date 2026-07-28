import asyncio
import os
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Iterable

from app.core.models import FileInfo, ValidateResult

default_chunk_size = 1024 * 1024


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

        # 再检查 filesize
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
        self.executor = executor or ThreadPoolExecutor()

    async def validate[T](self, file: FileInfo[T], chunk_size: int = default_chunk_size) -> ValidateResult[T]:
        return await self.loop.run_in_executor(self.executor, _validate, file, chunk_size)


def res_false_filter[T](results: Iterable[ValidateResult[T]]) -> list[ValidateResult[T]]:
    return [r for r in results if not r.result]


def res_true_filter[T](results: Iterable[ValidateResult[T]]) -> list[ValidateResult[T]]:
    return [r for r in results if r.result]
