import asyncio
import os
from concurrent.futures.thread import ThreadPoolExecutor
from stat import ST_SIZE, ST_MTIME
from typing import Iterable

from app.core.models import FileSpec, ValidateResult
from app.core.osio import OSFile

default_chunk_size = 4 * 1024 * 1024  # 4mb


def _compute_hash(filename, algorithm='sha1', chunk_size=default_chunk_size):
    import hashlib
    hasher = hashlib.new(algorithm)

    # fd = os.open(filename, os.O_RDONLY | os.O_BINARY)

    buffer = bytearray()
    buffer.resize(chunk_size)

    with OSFile.open(filename, os.O_RDONLY | os.O_BINARY) as fp:
        while n := fp.readinto(buffer):
            hasher.update(buffer[:n])

    return hasher


async def compute_hash(
        file, algorithm='sha1', chunk_size=default_chunk_size,
):
    return await asyncio.to_thread(
        _compute_hash,
        file, algorithm, chunk_size
    )


def _validate[T](filename, spec: FileSpec[T], chunk_size: int = default_chunk_size) -> ValidateResult[T]:
    real_size = None
    real_hash = None
    hex_checksum = None

    try:
        # 最先确保文件的存在性
        if not os.path.exists(filename):
            return ValidateResult(
                result=False,
                file=filename,
                spec=spec,
            )

        # 开始检查元数据
        stat = os.stat(filename)
        # - 检查 filesize
        filesize = spec.size
        if filesize is not None and filesize != (real_size := stat[ST_SIZE]):
            return ValidateResult(
                result=False,
                file=filename,
                spec=spec,
                size=real_size
            )
        # - 检查 mtime
        mtime = spec.last_modified
        if mtime is not None and mtime != (real_mtime := stat[ST_MTIME]):
            return ValidateResult(
                result=False,
                file=filename,
                spec=spec,
                size=real_size,
                last_modified=real_mtime
            )

        # 其次检查校验值
        checksum = spec.checksum
        algorithm = spec.algorithm

        if (
                checksum is not None

        ):
            real_hash = _compute_hash(
                filename,
                algorithm=algorithm,
                chunk_size=chunk_size
            )
            if real_hash.digest() != bytes.fromhex(checksum):
                return ValidateResult(
                    result=False,
                    file=filename,
                    spec=spec,
                    size=real_size,
                    checksum=real_hash.hexdigest()
                )

            hex_checksum = real_hash.hexdigest()

        return ValidateResult(
            result=True,
            file=filename,
            spec=spec,
            size=filesize,
            checksum=hex_checksum
        )
    except Exception as e:  # 发生任何异常都应该返回一个带错误信息的 Result 类型
        return ValidateResult(
            result=False,
            file=filename,
            spec=spec,
            size=real_size,
            checksum=hex_checksum,
            error=e
        )
def _spec_from_filename(filename, algorithm: str = 'sha1'):
    stat = os.stat(filename)
    size, mtime = stat[ST_SIZE], stat[ST_MTIME]
    # 计算 hash
    hash = _compute_hash(filename, algorithm)
    return FileSpec(
        size=size,
        checksum=hash.hexdigest(),
        algorithm=algorithm,
        last_modified=mtime
    )

class FileValidator:
    def __init__(self, executor=None, loop=None, max_workers=4):
        self.loop = loop or asyncio.get_event_loop()
        self.executor = executor or ThreadPoolExecutor(max_workers=max_workers)

    async def validate[T](self, filename, spec: FileSpec[T], chunk_size: int = default_chunk_size) -> ValidateResult[T]:
        return await self.loop.run_in_executor(self.executor, _validate, filename, spec, chunk_size)
    async def spec_from_file(self, filename, algorithm: str = 'sha1'):
        return await self.loop.run_in_executor(self.executor, _spec_from_filename, filename, algorithm)

def res_false_filter[T](results: Iterable[ValidateResult[T]]) -> list[ValidateResult[T]]:
    return [r for r in results if not r.result]


def res_true_filter[T](results: Iterable[ValidateResult[T]]) -> list[ValidateResult[T]]:
    return [r for r in results if r.result]
