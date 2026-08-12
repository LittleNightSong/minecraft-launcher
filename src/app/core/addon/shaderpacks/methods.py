from pathlib import Path
from zipfile import ZipFile


def is_shaderpack(filename: str | Path) -> bool:
    with ZipFile(filename, 'r') as zip:
        return 'shaders' in zip.infolist()
