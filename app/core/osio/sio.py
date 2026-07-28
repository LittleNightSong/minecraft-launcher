import os
from collections.abc import Buffer

from .os_extensions import read_all


class OSFile:
    def __init__(self, fd):
        self._fd = fd

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        return os.lseek(self._fd, offset, whence)

    def tell(self) -> int:
        return os.lseek(self._fd, 0, os.SEEK_CUR)

    def write(self, buffer: Buffer):
        os.write(self._fd, buffer)

    def read(self, n: int) -> bytes:
        return os.read(self._fd, n)

    def readinto(self, buffer: Buffer) -> int:
        return os.readinto(self._fd, buffer)

    def close(self):
        os.close(self._fd)

    def read_all(self, chunk_size: int = 8196) -> bytearray:
        return read_all(self._fd, chunk_size)

