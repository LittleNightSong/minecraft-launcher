from typing import Self, AsyncIterable

import msgspec
from loguru import logger

from app.core.common import VersionNotFound, write_model
from app.core.fetcher import Fetcher
from app.core.minecraft.matcher import match
from app.core.models import FileSpec
from app.core.models.assets_index import AssetsIndex
from app.core.models.env import Environment
from app.core.models.version_meta import VersionMeta
from app.core.models.version_spec import VersionSpec
from app.core.network import Session
from app.core.network.downloader import DownloadPlan
from app.core.third_party.mojang import MinecraftAPI
from .base_installer import Installer, PoolFileValidateRequest, ValidateRequest, LocalFileValidateRequest, \
    InstallContext


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
            return await self.fetcher.session.typed(entry.url)

        self.raw_version_meta = await self.fetcher.fetch_model_into_pool(
            key=f'versionmeta-{entry.id}.json',
            filespec=FileSpec(
                checksum=entry.sha1
            ),
            fetcher=_
        )

        self.version_meta: VersionMeta = (
            msgspec.convert(
                self.raw_version_meta,
                self.api.models.VersionMetaModel
            )).unify()

        aifile = self.version_meta.dependencies.assets_index

        async def _():
            return await self.fetcher.session.typed(aifile.url)

        self.raw_assets_index = await self.fetcher.fetch_model_into(
            filename=self.spec.repository.assets.index(aifile.id),
            filespec=FileSpec(
                checksum=aifile.sha1,
                size=aifile.size,
            ),
            fetcher=_
        )

        self.assets_index: AssetsIndex = (
            msgspec.convert(self.raw_assets_index, self.api.models.AssetIndexModel)
        ).unify()

    async def collect(self) -> AsyncIterable[ValidateRequest]:
        repository = self.spec.repository

        ins_dir = repository.versions.instance(self.spec.name)

        client = self.version_meta.downloads.client

        jar = f'client-{self.version_meta.version}.jar'
        yield PoolFileValidateRequest(
            jar,
            FileSpec(
                size=client.size,
                checksum=client.sha1,
                meta=DownloadPlan(
                    url=client.url,
                    estimated_size=client.size,
                    cache_name=jar,
                    target=ins_dir.main_file,
                )
            ),

            group='vanilla'
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
                yield LocalFileValidateRequest(
                    path,
                    FileSpec(
                        size=artifact.size,
                        checksum=artifact.sha1,
                        meta=DownloadPlan(
                            artifact.maven_url + artifact.path,
                            estimated_size=artifact.size,
                            target=path
                        )
                    ),
                    group='vanilla'
                )
            else:
                # 本地库，需要更复杂的判断
                if artifact := lib.artifact:
                    path = libs_dir.library_path(artifact.name)
                    yield LocalFileValidateRequest(
                        path,
                        FileSpec(
                            size=artifact.size,
                            checksum=artifact.sha1,
                            meta=DownloadPlan(
                                artifact.maven_url + artifact.path,
                                estimated_size=artifact.size,
                                target=path
                            )
                        ),
                        group='vanilla'

                    )

                try:
                    artifact = lib.get_native(self.env)
                    path = libs_dir.library_path(artifact.name)
                    yield LocalFileValidateRequest(
                        path,
                        FileSpec(
                            size=artifact.size,
                            checksum=artifact.sha1,
                            meta=DownloadPlan(
                                artifact.maven_url + artifact.path,
                                estimated_size=artifact.size,
                                target=path
                            )
                        ),
                        group='vanilla'

                    )
                except KeyError:
                    pass

        for asset in self.assets_index.objects:
            path = assets_dir.object(asset)
            yield LocalFileValidateRequest(
                path,
                FileSpec(
                    size=asset.size,
                    checksum=asset.hash,
                    meta=DownloadPlan(
                        self.api.asset_url(asset.hash),
                        estimated_size=asset.size,
                        target=path
                    )
                ),
                group='vanilla'
            )

    async def analyze(self, result) -> AsyncIterable[DownloadPlan]:
        # 分析逻辑很简单，几乎不需要什么操作
        for res in result.groups['vanilla']:  # 只处理我们自己的，防止串
            if not res.result.ok:
                logger.info("需要更新的文件：{}", res.result)
                yield res.result.spec.meta  # type: ignore

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
    async def get_installer(cls, context: InstallContext) -> Self | None:
        spec = context.spec
        if spec.loader is None:
            return cls(spec, context.session, context.fetcher, context.env)
        else:
            return None
