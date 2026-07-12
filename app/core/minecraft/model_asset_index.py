"""
资源索引模型模块。

定义了 Minecraft 资源索引文件的数据结构。
"""
import typing

from msgspec import Struct

if typing.TYPE_CHECKING:
    from app.core.common import FileInfo
    from app.core.resources.assets import AssetsDirectory


class _ObjectStruct(Struct):
    """
    资源文件对象结构（内部使用）。

    表示资源索引中的一个文件条目。

    :ivar hash: 文件的 SHA-1 哈希值
    :ivar size: 文件大小（单位：字节）
    """
    hash: str
    size: int


class AssetIndexModel(Struct):
    """
    资源索引模型。

    对应 Minecraft 资源索引 JSON 文件的结构。
    包含所有资源文件的哈希和大小信息。

    :ivar objects: 资源文件映射，键为文件路径，值为文件的哈希和大小
    """
    objects: dict[str, _ObjectStruct]

    def iter_object(self):
        """
        迭代所有资源文件条目。

        :yield: 三元组 (文件路径, SHA-1哈希, 文件大小)
        """
        for k, v in self.objects.items():
            yield k, v.hash, v.size

    def iter_fileinfo(self, assets_dir: AssetsDirectory):
        from app.core.common import FileInfo

        for k, h, s in self.iter_object():
            yield FileInfo(
                filename=assets_dir.object(h).path,
                hash=h, algorithm='sha1',
                size=s,
                meta=k
            )