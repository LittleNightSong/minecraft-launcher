from typing import Self

import msgspec

from app.core.common import VersionNotFound
from app.core.models import FileSpec
from app.core.models.assets_index import AssetsIndex
from app.core.models.methods import unify
from .base_installer import InstallContext
from .general_installer import GeneralInstaller


class VanillaInstaller(GeneralInstaller):
    prefix = 'vanilla'

    @classmethod
    async def get_installer(cls, context: InstallContext) -> Self | None:
        spec = context.spec
        if spec.loader is None:
            return cls(context)
        else:
            return None

    def __init__(self, context: InstallContext):
        super().__init__(context)
        self.raw_version_meta: dict | None = None
        self.raw_assets_index: dict | None = None

    async def fetch(self):
        manifest = await self.fetcher.fetch_model(
            fetcher=self.api.fetch_version_manifest,
            type=self.api.models.VersionManifestModel,
            key='versionmeta:manifest', ttl=3600
        )

        if self.spec.version == 'latest':
            self.spec.version = manifest.latest.release

        elif self.spec.version == 'latest-snapshot':
            self.spec.version = manifest.latest.snapshot

        self.spec.name = self.spec.name or self.spec.version

        # 获取版本描述文件
        entry = manifest.find(id=self.spec.version)
        if not entry:
            raise VersionNotFound(self.spec.version)

        raw_string_version_meta = await self.fetcher.fetch_raw_into_pool(
            key=f'versionmeta-{entry.id}.json',
            filespec=FileSpec(checksum=entry.sha1),
            fetcher=lambda: self.fetcher.session.read(entry.url)
        )

        self.raw_version_meta = msgspec.json.decode(raw_string_version_meta)

        self.version_meta = unify(self.raw_version_meta, self.api.models.VersionMetaModel)

        assets_index = self.version_meta.dependencies.assets_index

        self.raw_assets_index = await self.fetcher.fetch_model_into(
            filename=self.repository.assets.index(assets_index.id),
            filespec=FileSpec(
                checksum=assets_index.sha1,
                size=assets_index.size,
            ),
            fetcher=lambda: self.fetcher.session.typed(assets_index.url)
        )

        self.assets_index: AssetsIndex = unify(self.raw_assets_index, self.api.models.AssetIndexModel)
