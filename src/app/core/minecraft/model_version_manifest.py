"""
版本清单模型模块。

定义了 Minecraft 版本清单的数据结构，包含所有可用版本的列表和最新版本信息。
"""

from datetime import datetime
from typing import Generator

from msgspec import Struct, field
from typing_extensions import Literal

from .minecraft_version import MinecraftVersion


class LatestStruct(Struct):
    """
    最新版本信息。

    :ivar release: 最新正式版本的 ID
    :ivar snapshot: 最新快照版本的 ID
    """
    release: str
    snapshot: str


class VersionItemStruct(Struct):
    """
    版本清单中的单个版本条目。

    :ivar id: 版本 ID（如 "1.20.4"）
    :ivar type: 版本类型，可选 'snapshot'、'release'、'old_beta'、'old_alpha'
    :ivar url: 该版本元数据 JSON 文件的下载 URL
    :ivar time: 版本元数据更新时间
    :ivar release_time: 版本发布时间
    :ivar sha1: 版本元数据文件的 SHA-1 校验值
    :ivar compliance_level: Java 合规级别（可能为 None）
    """
    id: str
    type: Literal['snapshot', 'release', 'old_beta', 'old_alpha']
    url: str
    time: datetime
    release_time: datetime = field(name='releaseTime')
    sha1: str
    compliance_level: int | None = field(default=None, name='complianceLevel')


class VersionManifestModel(Struct):
    """
    版本清单模型。

    对应 Mojang 官方版本清单 JSON 文件的结构。

    :ivar latest: 最新版本信息
    :ivar versions: 所有可用版本的列表
    """
    latest: LatestStruct
    versions: list[VersionItemStruct]

    @property
    def latest_items(self) -> Generator[VersionItemStruct, None, None]:
        cnt = 0
        for v in self.versions:
            if cnt == 2:
                return
            if v.id == self.latest.release:
                yield v
                cnt += 1
                continue
            if v.id == self.latest.snapshot:
                yield v
                cnt += 1
                continue

    def find(self, id: str, type: Literal['all', 'snapshot', 'release'] = 'all') -> VersionItemStruct | None:
        """
        在版本清单中查找指定 ID 的版本。

        :param id: 版本 ID
        :param type: 版本类型过滤，'all' 表示不过滤
        :return: 找到的版本条目，未找到则返回 None
        """
        for v in self:
            if type != 'all' and v.type != type:
                continue

            if v.id == id:
                return v

        return None

    def build_mapping(self) -> dict[str, VersionItemStruct]:
        """
        构建版本 ID 到版本条目的映射字典。

        :return: 字典，键为版本 ID，值为对应的版本条目
        """
        return {v.id: v for v in self}

    def separate(self, merge_snapshots=True) -> dict[str, list[MinecraftVersion]]:
        """
        分解清单文件
        返回一个字典
        包含一下字段:

        - rc
        - pre
        - snapshot
        - release
        - april fool
        - old
        """
        version_groups = {
            'rc': [],
            'pre': [],
            'snapshot': [],
            'snapshot(legacy)': [],
            'release': [],
            'april fool': [],
            'old': [],
        }

        if not merge_snapshots:
            for v in self:
                mc_version = MinecraftVersion(v.id)
                version_groups[mc_version.type].append(mc_version)
        else:
            for v in self:
                mc_version = MinecraftVersion(v.id)
                version_groups[mc_version.type.removesuffix('(legacy)')].append(mc_version)

        return version_groups

    def __iter__(self):
        return iter(self.versions)
