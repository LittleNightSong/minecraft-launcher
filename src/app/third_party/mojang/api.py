"""
Minecraft API 客户端模块。

提供与 Minecraft 官方 API 交互的功能，包括版本清单获取、资源文件下载链接生成、
玩家 UUID 查询等核心功能。
"""

import hashlib
import uuid
from itertools import batched
from typing import Iterable
from uuid import UUID

import msgspec
import niquests

from app.core.models import Library
from app.core.network import Session
from . import models as _models
from .models import PlayerProfile, TexturesPropertyStruct, VersionManifestModel, VersionMetaModel, AssetIndexModel


class MinecraftAPI:
    """
    Minecraft 官方 API 客户端。

    封装了与 Mojang 及 Minecraft 相关 API 的交互逻辑，包括：
    - 版本清单获取
    - 资源文件 URL 生成
    - 库文件 URL 生成
    - 玩家 UUID 查询（在线/离线）
    """

    models = _models

    url_version_manifest = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    url_maven = "https://libraries.minecraft.net"
    url_asset_root = "https://resources.download.minecraft.net"

    def __init__(self, session: Session):
        """
        初始化 Minecraft API 客户端。

        :param session: 网络会话实例，用于发起 HTTP 请求
        """
        self.session = session

    async def fetch_version_manifest(self) -> VersionManifestModel:
        """
        获取 Minecraft 版本清单。

        从 Mojang 官方元数据服务获取所有可用游戏版本的列表和元信息。

        :return: 版本清单模型对象
        """

        return await self.session.typed(
            url=self.url_version_manifest,
            type=VersionManifestModel
        )

    def asset_url(self, hash: str) -> str:
        """
        生成资源文件的下载 URL。

        根据文件的 SHA-1 哈希值生成 Minecraft 资源 CDN 的下载地址。
        资源文件按照哈希值前两位分目录存储。

        :param hash: 资源文件的 SHA-1 哈希值
        :return: 资源文件的下载 URL
        """
        hash = str(hash).lower()
        return f'{self.url_asset_root}/{hash[:2]}/{hash}'
        # return f'https://bmclapi2.bangbang93.com/assets/{hash[:2]}/{hash}'  # 临时镜像源

    def library_url_by_path(self, path: str) -> str:
        """
        通过库文件的相对路径生成下载 URL。

        :param path: 库文件在 Maven 仓库中的相对路径
        :return: 库文件的下载 URL
        """
        return f'{self.url_maven}/{path}'

    def library_url_by_name(self, name: str) -> str:
        """
        通过库的 Maven 坐标生成下载 URL。

        :param name: 库的 Maven 坐标（groupId:artifactId:version）
        :return: 库文件的下载 URL
        """
        return f'{self.url_maven}/{Library(str(name)).path}'

    def calc_player_uuid(self, name: str) -> UUID:
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

    async def query_player_uuid(self, name: str) -> UUID:
        """
        从 Mojang API 查询玩家的在线 UUID。

        :param name: 玩家名称
        :return: 玩家的在线 UUID
        :raises niquests.HTTPError: 当 API 请求失败时抛出
        """
        uuid_string = (
            await self.session.typed(
                "https://api.mojang.com/users/profiles/minecraft/{}", name,
                type=dict
            )
        )['id']
        return UUID(uuid_string)

    async def get_player_uuid(self, name: str) -> UUID:
        """
        获取玩家 UUID，支持在线查询和离线回退。

        优先尝试在线查询，如果失败且允许回退，则生成离线 UUID。

        :param name: 玩家名称
        :return: 玩家的 UUID
        :raises niquests.HTTPError: 当在线查询失败且非无此用户的问题时抛出
        """
        try:
            return await self.query_player_uuid(name)
        except niquests.HTTPError as e:
            if e.response.status_code == 404:
                return self.calc_player_uuid(name)
            else:
                raise e

    async def query_player_uuids(self, names: Iterable[str], strict: bool = False) -> dict[str, UUID]:
        """
        批量获取玩家的 uuid
        :param names: 一个可迭代对象，包含多个名称字符串
        :param strict: Mojang API 严格要求每次请求的查询数不得大于 10，如果不启用 strict，将自动分批获取，否则抛出 OverflowError
        :return: 一个字典，包含 name -> uuid 的映射
        :raise OverflowError: 当传入的名称数量大于限制且指定了 strict 模式，将抛出此错误
        :raise niquests.HTTPError: 当 API 请求失败时抛出
        """
        names = tuple(names)
        if strict and len(names) > 10:
            raise OverflowError()

        result = {}
        for chunk in batched(names, 10):
            resp = await self.session.typed(
                "https://api.mojang.com/profiles/minecraft",
                method='POST',
                data=msgspec.json.encode(chunk),
                type=list[dict]
            )

            for i in resp:
                result[i['name']] = UUID(i['id'])

        return result

    async def query_player_name(self, uuid: UUID | str):
        """
        通过 uuid 查询一个玩家的名称
        :param uuid: 玩家的 UUID
        :return: 玩家的名称
        """
        uuid = uuid if isinstance(uuid, UUID) else UUID(uuid)
        resp = await self.session.typed(
            "https://api.minecraftservices.com/minecraft/profile/lookup/{}", uuid,
            type=dict
        )
        return resp['name']

    async def fetch_player_profile(self, uuid: UUID | str):
        """
        获取玩家的公开个人资料
        :param uuid: 玩家的 UUID
        :return: 玩家的个人资料对象 `PlayerProfile`
        """
        uuid = uuid if isinstance(uuid, UUID) else UUID(uuid)
        return await self.session.typed(
            "https://sessionserver.mojang.com/session/minecraft/profile/{}", uuid,
            type=PlayerProfile
        )

    async def fetch_player_skin_url(self, uuid: uuid | str):
        """
        获取玩家皮肤文件的url
        :param uuid: 玩家的 UUID
        :return: 玩家皮肤 URL
        """
        profile = await self.fetch_player_profile(uuid)
        for i in profile.properties:
            if isinstance(i, TexturesPropertyStruct):
                return i.decode_value().textures.SKIN.url
        return None

    async def fetch_player_cape_url(self, uuid: UUID | str) -> str | None:
        """
        获取玩家披风文件的 URL
        :param uuid: 玩家的 URL
        :return: 当玩家披风存在时，返回一个 URL，否则 None
        """
        profile = await self.fetch_player_profile(uuid)
        for i in profile.properties:
            if isinstance(i, TexturesPropertyStruct):
                cape = i.decode_value().textures.CAPE
                if cape:
                    return cape.url
        return None

    async def fetch_player_skin(self, uuid: UUID | str) -> bytes:
        """
        获取玩家皮肤纹理文件
        :param uuid: 玩家 UUID
        :return: 文件的原始字节流
        """
        url = await self.fetch_player_skin_url(uuid)
        if url:
            data = await self.session.read(url)
            if data:
                return data
            else:
                raise ValueError("No content")
        else:
            raise ValueError("No content")

    async def fetch_player_cape(self, uuid: UUID | str):
        """
        获取玩家披风纹理文件
        :param uuid: 玩家 UUID
        :return: 文件的原始字节流
        """
        url = await self.fetch_player_cape_url(uuid)
        if url:
            data = await self.session.read(url)
            if data:
                return data
            else:
                raise ValueError("No content")
        else:
            raise ValueError("No content")

    async def fetch_version_meta(self, url: str) -> VersionMetaModel:
        return await self.session.typed(
            url,
            type=VersionMetaModel
        )

    async def fetch_asset_index(self, url):
        return await self.session.typed(
            url,
            type=AssetIndexModel
        )
