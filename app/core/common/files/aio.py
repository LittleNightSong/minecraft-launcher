import asyncio
import os
from asyncio import AbstractEventLoop
from collections.abc import Buffer
from concurrent.futures import Executor
from concurrent.futures.thread import ThreadPoolExecutor

from . import os_extensions

STOP = object()


class AioFile:  # 一个非常简单的 async file I/O wrapper
    __slots__ = ("_fd", "_loop", "_executor", "_worker", "_queue", "_running")

    def __init__(self, fd, executor: Executor | None = None, loop=None, max_tasks=0):
        self._fd = fd
        self._executor = executor or ThreadPoolExecutor()
        self._loop = loop or asyncio.get_event_loop()

    async def _run(self, fn, *args):  # 并行执行，不关心并发的数量，也不限制并发数
        if not self._running:
            raise RuntimeError("The worker has been closed")

        return await self._loop.run_in_executor(
            self._executor,
            fn, *args
        )

    async def close(self):
        if self._fd:
            os.close(self._fd)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def __del__(self):
        if self._fd is not None:
            os.close(self._fd)

    @property
    def fileno(self):
        return self._fd

    async def write(self, data: Buffer) -> int:
        return await self._run(os.write, self._fd, data)

    async def read(self, n: int) -> bytes:
        return await self._run(os.read, self._fd, n)

    async def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        return await self._run(os.lseek, self._fd, offset, whence)

    async def tell(self) -> int:
        return await self._run(os.lseek, self._fd, 0, os.SEEK_CUR)  # 不移动指针，返回指针位置

    async def truncate(self, size: int) -> None:
        await self._run(os.ftruncate, self._fd, size)

    async def sync(self) -> None:
        await self._run(os.fsync, self._fd)

    async def datasync(self) -> None:
        await self._run(os.fdatasync, self._fd)

    async def readinto(self, buffer: Buffer, n: int | None = None) -> int:
        if n is not None:
            buffer = memoryview(buffer)[:n]  # 自动截取一个子缓冲区

        return await self._run(os.readinto, self._fd, buffer)

    async def read_all(self, buffer_size: int = 8192):
        return await self._run(os_extensions.read_all, self._fd, buffer_size)

    async def join(self):
        await self._queue.join()

    @classmethod
    def open(
            cls,
            path, flags, mode=0o777, *, dir_fd: int | None = None,
            executor: Executor | None = None, loop: AbstractEventLoop | None = None
    ) -> AioFile:
        return cls(
            os.open(
                path, flags, mode, dir_fd=dir_fd
            ),
            executor=executor, loop=loop
        )
