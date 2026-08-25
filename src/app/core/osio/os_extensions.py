import os
import shutil
from typing import Literal


def read_all(fd, buffer_size=8192):
    data = bytearray()
    buffer = bytearray(buffer_size)

    while n := os.readinto(fd, buffer):
        data.extend(buffer[:n])

    return bytes(data)


def link_file(src, dst, mode: Literal['hardlink', 'symlink', 'copy'], force=True):
    if force:
        safe_unlink(dst)
    match mode:
        case 'hardlink':
            os.link(src, dst)
        case 'symlink':
            os.symlink(src, dst)
        case 'copy':
            shutil.copy2(src, dst)


def safe_unlink(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def safe_mkdir(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        pass
