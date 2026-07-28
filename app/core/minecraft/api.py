"""
Minecraft API 客户端模块。

提供与 Minecraft 官方 API 交互的功能，包括版本清单获取、资源文件下载链接生成、
玩家 UUID 查询等核心功能。
"""

import hashlib
import uuid
from uuid import UUID

import niquests

from app.core.network import Session
from .model_version_manifest import VersionManifestModel
from ..cacher.model_cacher import CacheManager
from ..models.library import Library


class MinecraftAPI:
    """
    Minecraft 官方 API 客户端。

    封装了与 Mojang 及 Minecraft 相关 API 的交互逻辑，包括：
    - 版本清单获取
    - 资源文件 URL 生成
    - 库文件 URL 生成
    - 玩家 UUID 查询（在线/离线）
    """

    def __init__(self, session: Session, cacher: CacheManager | None = None):
        """
        初始化 Minecraft API 客户端。

        :param session: 网络会话实例，用于发起 HTTP 请求
        """
        self.session = session
        self.cacher = cacher

    async def get_version_manifest(self) -> VersionManifestModel:
        """
        获取 Minecraft 版本清单。

        从 Mojang 官方元数据服务获取所有可用游戏版本的列表和元信息。

        :return: 版本清单模型对象
        """
        if self.cacher is None:
            manifest = await self.session.call(
                url=self.version_manifest_url,
                type=VersionManifestModel
            )
        else:
            manifest = self.cacher.get_model(key='versionmeta:manifest', type=VersionManifestModel)
            if manifest is None:
                manifest =  await self.session.call(
                    url=self.version_manifest_url,
                    type=VersionManifestModel
                )
                self.cacher.set_model(key='versionmeta:manifest', value=manifest, ttl=300)

        return manifest

    @property
    def version_manifest_url(self):
        return "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

    def asset_url(self, hash: str) -> str:
        """
        生成资源文件的下载 URL。

        根据文件的 SHA-1 哈希值生成 Minecraft 资源 CDN 的下载地址。
        资源文件按照哈希值前两位分目录存储。

        :param hash: 资源文件的 SHA-1 哈希值
        :return: 资源文件的下载 URL
        """
        hash = str(hash).lower()
        return f'https://resources.download.minecraft.net/{hash[:2]}/{hash}'
        # return f'https://bmclapi2.bangbang93.com/assets/{hash[:2]}/{hash}'  # 临时镜像源

    def library_url_by_path(self, path: str) -> str:
        """
        通过库文件的相对路径生成下载 URL。

        :param path: 库文件在 Maven 仓库中的相对路径
        :return: 库文件的下载 URL
        """
        return f'https://libraries.minecraft.net/{path}'

    def library_url_by_name(self, name: str) -> str:
        """
        通过库的 Maven 坐标生成下载 URL。

        :param name: 库的 Maven 坐标（groupId:artifactId:version）
        :return: 库文件的下载 URL
        """
        return f'https://libraries.minecraft.net/{Library(str(name)).path}'

    def get_uuid_by_name_offline(self, name: str) -> UUID:
        """
        根据玩家名称生成离线模式 UUID。

        离线模式 UUID 基于 "OfflinePlayer:<name>" 的 MD5 哈希生成，
        符合 UUID v3 规范。

        :param name: 玩家名称
        :return: 离线模式 UUID
        """
        return uuid.UUID(
            bytes=hashlib.md5(f'OfflinePlayer:{name}'.encode()).digest(), version=3
        )

    async def get_uuid_by_name_online(self, name: str) -> UUID:
        """
        从 Mojang API 查询玩家的在线 UUID。

        :param name: 玩家名称
        :return: 玩家的在线 UUID
        :raises niquests.HTTPError: 当 API 请求失败时抛出
        """
        uuid_string = (await self.session.call(
            "https://api.mojang.com/users/profiles/minecraft/{}", name,
            type=dict
        ))['id']
        return UUID(uuid_string)

    async def get_uuid_by_name(self, name: str) -> UUID:
        """
        获取玩家 UUID，支持在线查询和离线回退。

        优先尝试在线查询，如果失败且允许回退，则生成离线 UUID。

        :param name: 玩家名称
        :return: 玩家的 UUID
        :raises niquests.HTTPError: 当在线查询失败且非无此用户的问题时抛出
        """
        try:
            return await self.get_uuid_by_name_online(name)
        except niquests.HTTPError as e:
            if e.response.status_code == 404:
                return self.get_uuid_by_name_offline(name)
            else:
                raise e
