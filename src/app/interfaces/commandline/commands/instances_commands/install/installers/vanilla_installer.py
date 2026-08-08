from os import PathLike
from typing import Self, AsyncIterable

import msgspec

from app.core.common import VersionNotFound, write_model
from app.core.fetcher import Fetcher
from app.core.minecraft.matcher import match
from app.core.models.env import Environment
from app.core.network import Session
from app.core.models.version_meta import VersionMeta
from app.core.models.version_spec import VersionSpec
from app.core.models.assets_index import AssetsIndex
from app.core.models import FileSpec, ValidateResult
from app.core.network.downloader import DownloadPlan
from app.core.third_party.mojang import MinecraftAPI
from .base_installer import Installer


class VanillaInstaller(Installer):
    spec: VersionSpec
    session: Session
    fetcher: Fetcher
    env: Environment

    version_meta: VersionMeta
    assets_index: AssetsIndex

    def __init__(self, spec, session, fetcher, env):
        self.raw_version_meta = None
        self.raw_assets_index = None
        self.spec = spec
        self.session = session
        self.api = MinecraftAPI(session)
        self.fetcher = fetcher
        self.env = env

        self.version_meta = None
        self.assets_index = None

    async def init(self):
        (
            self.fetcher.model_cacher
            .set_default_ttl('versionmeta', 3600)
        )

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

        async def _():
            return await self.api.fetch_version_meta(entry.url)

        self.raw_version_meta = await self.fetcher.fetch_model_into_pool(
            key=f'versionmeta:{entry.id}',
            filespec=FileSpec(
                checksum=entry.sha1
            ),
            fetcher=_
        )

        self.version_meta: VersionMeta = (
            msgspec.convert(self.raw_version_meta, self.api.models.VersionMetaModel)).unify()

        dli = self.version_meta.dependencies.assets_index

        async def _():
            return await self.api.fetch_asset_index(dli.url)

        self.raw_assets_index = await self.fetcher.fetch_model_into(
            filename=self.spec.repository.assets.index(dli.id),
            filespec=FileSpec(
                checksum=dli.sha1,
                size=dli.size,
            ),
            fetcher=_
        )

        self.assets_index: AssetsIndex = (
            msgspec.convert(self.raw_assets_index, self.api.models.AssetIndexModel)
        ).unify()

    async def collect(self) -> AsyncIterable[tuple[str | PathLike, FileSpec]]:
        repository = self.spec.repository

        ins_dir = repository.versions.instance(self.spec.name)

        client = self.version_meta.downloads.client

        yield ins_dir.main_file, FileSpec(
            size=client.size,
            checksum=client.sha1,
            meta=DownloadPlan(
                url=client.url,
                estimated_size=client.size,
                cache_name=f'client:{self.version_meta.version}',
                target=ins_dir.main_file,
            )
        )

        dep = self.version_meta.dependencies
        libs_dir = repository.libraries
        assets_dir = repository.assets

        for lib in dep.libraries:
            # 先匹配 rules
            if lib.rules and not match(lib.rules, self.env, {}):
                continue

            if isinstance(lib, dep.CommonLibraryStruct):
                artifact = lib.artifact
                path = libs_dir.library_path(artifact.name)
                yield path, FileSpec(
                    size=artifact.size,
                    checksum=artifact.sha1,
                    meta=DownloadPlan(
                        artifact.maven_url + artifact.path,
                        estimated_size=artifact.size,
                        target=path
                    )
                )

            else:
                # 本地库，需要更复杂的判断
                if artifact := lib.artifact:
                    path = libs_dir.library_path(artifact.name)
                    yield path, FileSpec(
                        size=artifact.size,
                        checksum=artifact.sha1,
                        meta=DownloadPlan(
                            artifact.maven_url + artifact.path,
                            estimated_size=artifact.size,
                            target=path
                        )
                    )

                try:
                    artifact = lib.get_native(self.env)
                    path = libs_dir.library_path(artifact.name)
                    yield path, FileSpec(
                        size=artifact.size,
                        checksum=artifact.sha1,
                        meta=DownloadPlan(
                            artifact.maven_url + artifact.path,
                            estimated_size=artifact.size,
                            target=path
                        )
                    )
                except KeyError:
                    pass

        for asset in self.assets_index.objects:
            path = assets_dir.object(asset)
            yield path, FileSpec(
                size=asset.size,
                checksum=asset.hash,
                meta=DownloadPlan(
                    self.api.asset_url(asset.hash),
                    estimated_size=asset.size,
                    target=path
                )
            )

    async def analyze(self, result: list[ValidateResult[DownloadPlan]]) -> AsyncIterable[DownloadPlan]:
        # 分析逻辑很简单，几乎不需要什么操作
        for res in result:
            if not res.ok:
                yield res.spec.meta

    async def post_install(self):
        # 将版本 json 等文件放回 ins_dir
        ins_dir = self.spec.repository.versions.instance(self.spec.name)
        write_model(ins_dir.meta_file, self.raw_version_meta)
        write_model(
            ins_dir / f'{self.spec.name}.mpk',
            self.version_meta,
            encoder=msgspec.msgpack.encode
        )

    @classmethod
    async def get_installer(
            cls,
            spec: VersionSpec, session: Session, fetcher: Fetcher, env: Environment
    ) -> Self | None:
        if spec.loader is None:
            return cls(spec, session, fetcher, env)
        else:
            return None
