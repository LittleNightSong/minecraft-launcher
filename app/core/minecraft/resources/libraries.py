import typing
from pathlib import Path
from typing import Iterable

from app.core.minecraft.matcher import RulesMatcher
from app.core.minecraft.resources.base import BaseDirectory
from app.core.models import Library

if typing.TYPE_CHECKING:
    from app.core.minecraft.model_version_meta import StandardLibraryStruct
    from app.core.common import FileInfo


class LibrariesDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

    def library(self, name: str):
        return Library(name, self.path)

    def library_path(self, name: str):
        return self.library(name).fullpath

    # @trace
    async def check(self, name, hash, size=None):
        return self.library(name).check(hash, size)

    def get_library_files(self, libraries: Iterable[StandardLibraryStruct], matcher: RulesMatcher) -> list[FileInfo]:
        """
        获取当前平台所需的所有依赖库的文件, 包括 natives 库 (如果有的话)
        :param libraries: 依赖库模型结构体
        :param matcher: 规则匹配器对象
        :return: 所需文件的 FileInfo 对象列表
        """
        from app.core.models import FileInfo
        return [
            FileInfo.from_downloads_struct(
                downloads=dl,
                filename=self / dl.path,
                meta=Library(name)
            )
            for lib in libraries
            for dl, name in lib.collect_files(matcher)
        ]
