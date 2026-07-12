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

    def __init__(self, fd, executor: Executor | None = None, loop=None):
        self._fd = fd
        self._executor = executor or ThreadPoolExecutor()
        self._loop = loop or asyncio.get_event_loop()

    async def _run(self, fn, *args):
        return await self._loop.run_in_executor(
            self._executor,
            fn, *args
        )

    async def close(self):
        if self._fd:
            os.close(self._fd)
            self._fd = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def __del__(self):
        if self._fd:
            os.close(self._fd)

    @property
    def fileno(self):
        return self._fd

    async def write(self, data: Buffer) -> int:
        """
        写入数据，返回实际写入的数据长度
        :param data: 待写入数据
        :return: 实际写入数据的长度
        """
        return await self._run(os.write, self._fd, data)

    async def read(self, n: int) -> bytes:
        """
        读取至多 n 个数据
        :param n: 数据最大长度
        :return: 读取到的数据
        """
        return await self._run(os.read, self._fd, n)

    async def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        """
        设置文件偏移量
        :param offset: 偏移量值
        :param whence: 定位方式
        os.SEEK_SET 表示从文件开头定位(绝对位置);
        os.SEEK_CUR 表示相对于当前偏移量定位;
        os.SEEK_END 表示从文件末尾定位
        :return:
        """
        return await self._run(os.lseek, self._fd, offset, whence)

    async def tell(self) -> int:
        """
        获取当前偏移量大小(绝对位置)
        :return: 当前偏移量
        """
        return await self._run(os.lseek, self._fd, 0, os.SEEK_CUR)  # 不移动指针，返回指针位置

    async def truncate(self, size: int) -> None:
        """
        截断文件到 size 大小
        :param size: 目标大小
        :return: None
        """
        await self._run(os.ftruncate, self._fd, size)

    async def sync(self) -> None:
        """
        同步文件信息,包括文件元数据和待写入磁盘的数据
        :return:
        """
        await self._run(os.fsync, self._fd)

    async def datasync(self) -> None:
        """
        同步数据写入,保证数据已从系统缓冲区写入磁盘
        :return: None
        """
        await self._run(os.fdatasync, self._fd)

    async def readinto(self, buffer: Buffer) -> int:
        """
        读取一定的数据, 并填充进缓冲区. 至多读取缓冲区大小个字节, 并返回实际读取的数据的长度
        :param buffer: 缓冲区
        :return: 实际读取数据的长度
        """

        return await self._run(os.readinto, self._fd, buffer)

    async def read_all(self, buffer_size: int = 8192):
        """
        读取文件的所有内容, 内部使用分批读取
        :param buffer_size: 每批数据的大小
        :return: 累计的数据
        """
        return await self._run(os_extensions.read_all, self._fd, buffer_size)

    async def join(self):
        await self._queue.join()

    @classmethod
    def open(
            cls,
            path, flags, mode=0o777, *, dir_fd: int | None = None,
            executor: Executor | None = None, loop: AbstractEventLoop | None = None
    ) -> AioFile:
        """
        打开文件
        详细文档参见 `os.open`
        返回一个 AioFile 对象
        """
        return cls(
            os.open(
                path, flags, mode, dir_fd=dir_fd
            ),
            executor=executor, loop=loop
        )
