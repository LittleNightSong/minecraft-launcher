from typing import Self

import msgspec

from app.core.common.errors import VersionNotFound, VersionNotSupported
from app.core.i18n import tr
from app.impls.installers.base_installer import InstallContext
from app.impls.installers.vanilla_installer import VanillaInstaller
from app.third_party.fabric_meta.api import FabricMetaV2


class FabricInstaller(VanillaInstaller):
    prefix = 'fabric'

    @classmethod
    async def get_installer(cls, context: InstallContext) -> Self | None:
        spec = context.spec

        if spec.loader and spec.loader == 'fabric':
            return cls(context)

        return None

    def __init__(self, context: InstallContext):
        super().__init__(context)

        self.fabric_api = FabricMetaV2(self.session)

        self.raw_fabric_libs: list | None = None

    async def fetch(self):
        no_name = self.spec.name is None

        await super().fetch()

        self.interactor.status(tr("获取 Fabric 元数据"))

        # 获取 fabric 清单
        game_ver = self.version_meta.version
        loader_ver = self.spec.loader_version

        manifest = await self.fetcher.fetch_model(
            key=f'fabric-meta:loaders:{game_ver}',
            fetcher=lambda: self.fabric_api.fetch_loaders_by_game(game_ver),
            ttl=3600, type=list[self.fabric_api.models.LoaderDetailListItem]
        )

        if not manifest:
            raise VersionNotSupported('Fabric 在选定的 Minecraft {} 中不可用', game_ver)

        entry = None

        if loader_ver is None:
            entry = manifest[0]
            for i in manifest:
                if i.loader.stable:
                    entry = i
                    break
        else:
            for i in manifest:
                if i.loader.version == loader_ver:
                    entry = i
                    break

        if entry is None:
            raise VersionNotFound(f"fabric-{loader_ver or 'latest-stable'}")

        loader_ver = entry.loader.version

        # 获取 profile
        _T = self.fabric_api.models.LoaderProfile
        profile: _T = await self.fetcher.fetch_model_into_pool(
            key=f'fabric-profile-{game_ver}-{loader_ver}.json',
            fetcher=lambda: self.fabric_api.fetch_loader_profile(game_ver, loader_ver),
            type=_T
        )

        # 将这个信息合并到 version-meta 中

        # 合并 libraries
        self.version_meta.dependencies.libraries.extend(
            i.unify() for i in profile.libraries
        )

        # 合并主类名
        self.version_meta.main_class = profile.main_class

        # 合并启动参数
        arguments = self.version_meta.arguments
        profile_args = profile.arguments.unify()

        arguments.game.extend(profile_args.game)
        arguments.jvm.extend(profile_args.jvm)

        # 我们为了兼容性，得同时更新 raw_version_meta
        raw_version_meta = self.raw_version_meta
        raw_version_meta['libraries'].extend(
            msgspec.to_builtins(profile.libraries)
        )
        raw_version_meta['mainClass'] = profile.main_class
        _ = raw_version_meta['arguments']
        _['game'].extend(msgspec.to_builtins(profile.arguments.game))
        _['jvm'].extend(msgspec.to_builtins(profile.arguments.jvm))

        # 最后需要改掉 spec 中的 name
        if no_name:
            self.spec.name = f'{game_ver}-fabric-{loader_ver}'

        # 在 version-meta 中添加 loader 信息
        self.version_meta.loader = 'fabric'
        self.version_meta.loader_version = loader_ver

        # 修补正式完成了

        self.spec.loader = 'fabric'
        self.spec.loader_version = loader_ver

