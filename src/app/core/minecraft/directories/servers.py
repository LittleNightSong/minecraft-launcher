from pathlib import Path

from .base import BaseDirectory


class ServersDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

