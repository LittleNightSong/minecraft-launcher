import os

from .aio import AsyncOSFile
from .sio import OSFile


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
