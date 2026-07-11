import hashlib
import uuid
from uuid import UUID

import niquests

from app.core.minecraft import VersionManifestModel
from app.core.network import Session
from app.core.resources.libraries import Library


class MinecraftAPI:
    def __init__(self, session: Session):
        self.session = session

    async def get_version_manifest(self) -> VersionManifestModel:
        return await self.session.call(
            url="https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
            type=VersionManifestModel
        )

    def asset_url(self, hash):
        hash = str(hash).lower()
        return f'https://resources.download.minecraft.net/{hash[:2]}/{hash}'
        # return f'https://bmclapi2.bangbang93.com/assets/{hash[:2]}/{hash}'  # 临时镜像源

    def library_url_by_path(self, path):
        return f'https://libraries.minecraft.net/{path}'

    def library_url_by_name(self, name):
        return f'https://libraries.minecraft.net/{Library(str(name)).path}'

    def get_uuid_by_name_offline(self, name):
        return uuid.UUID(
            bytes=hashlib.md5(f'OfflinePlayer:{name}'.encode()).digest(), version=3
        )

    async def get_uuid_by_name_online(self, name):
        uuid_string = (await self.session.call(
            "https://api.mojang.com/users/profiles/minecraft/{}", name,
            type=dict
        ))['id']
        return UUID(uuid_string)

    async def get_uuid_by_name(self, name, fallback=True):
        try:
            return await self.get_uuid_by_name_online(name)
        except niquests.HTTPError as e:
            if e.response.status_code == 404 and fallback:
                return self.get_uuid_by_name_offline(name)
            else:
                raise e
