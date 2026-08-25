from abc import abstractmethod
from typing import Self, AsyncIterable

import msgspec
from loguru import logger
from niquests.utils import urljoin_safe

from app.core.common import VersionNotFound, write_model
from app.core.minecraft.matcher import match
from app.core.models import FileSpec
from app.core.models.assets_index import AssetsIndex
from app.core.models.methods import unify
from app.core.models.version_meta import VersionMeta, CommonLibraryStruct
from app.core.network.downloader import HTTPDownloadPlan
from app.core.osio import link_file
from app.third_party.mojang import MinecraftAPI
from .base_installer import Installer, InstallContext, LocalFileValidateRequest, PoolFileValidateRequest, \
    ValidateRequest
from ...core.minecraft import InstanceDirectory


class GeneralInstaller(Installer):
    def __init__(self, context: InstallContext):
        self.context = context

        self.spec = context.spec
        self.env = context.env

        self.session = context.session
        self.api = MinecraftAPI(context.session)
        self.fetcher = context.fetcher

        self.repository = context.repository

        self.interactor = context.interactor

        self.version_meta: VersionMeta | None = None
        self.assets_index: AssetsIndex | None = None

        self.instance_dir: InstanceDirectory | None = None

    async def init(self):
        (
            self.fetcher.model_cacher
            .set_default_ttl('versionmeta', 3600)
        )

    @classmethod
    @abstractmethod
    async def get_installer(cls, context: InstallContext) -> Self | None:
        ...

    async def fetch(self):
        ...

    async def collect(self) -> AsyncIterable[ValidateRequest]:
        assert self.version_meta

        repository = self.repository
        client = self.version_meta.downloads.client

        jar = f'client-{self.version_meta.version}.jar'
        yield PoolFileValidateRequest(
            jar,
            FileSpec(
                size=client.size,
                checksum=client.sha1,
                meta=HTTPDownloadPlan(
                    url=client.url,
                    estimated_size=client.size,
                    target=jar,
                    is_cache=True
                )
            ),

            group='vanilla',
        )

        dep = self.version_meta.dependencies
        libs_dir = repository.libraries
        assets_dir = repository.assets

        def make_library_request(artifact):
            path = libs_dir.library_path(artifact.name)
            return LocalFileValidateRequest(
                path,
                FileSpec(
                    size=artifact.size,
                    checksum=artifact.sha1,
                    meta=HTTPDownloadPlan(
                        urljoin_safe(artifact.maven_url, str(artifact.path).removeprefix('/')),
                        estimated_size=artifact.size,
                        target=path
                    )
                ),
                group='vanilla'
            )

        for lib in dep.libraries:
            # 先匹配 rules
            if lib.rules and not match(lib.rules, self.env, {}):
                continue

            if isinstance(lib, CommonLibraryStruct):
                yield make_library_request(lib.artifact)
            else:
                # 本地库，需要更复杂的判断
                if artifact := lib.artifact:
                    yield make_library_request(artifact)

                try:
                    artifact = lib.get_native(self.env)  # 尝试直接获取 native 库，如果没有，会报错 KeyError
                    yield make_library_request(artifact)
                except KeyError:
                    pass

        assert self.assets_index
        for asset in self.assets_index.objects:
            asset_path = assets_dir.objects.path / asset.path
            yield LocalFileValidateRequest(
                asset_path,
                FileSpec(
                    size=asset.size,
                    checksum=asset.hash,
                    meta=HTTPDownloadPlan(
                        self.api.asset_url(asset.hash),
                        estimated_size=asset.size,
                        target=asset_path
                    )
                ),
                group='vanilla'
            )

    async def pre_download(self, result) -> AsyncIterable[HTTPDownloadPlan]:
        # 分析逻辑很简单，几乎不需要什么操作
        for res in result.groups['vanilla']:  # 只处理我们自己的，防止串
            if not res.result.ok:
                logger.info("需要更新的文件：{}", res.result)
                yield res.result.spec.meta  # type: ignore

    async def post_install(self):
        # post-install 钩子的一个特点就是不会被 Ctrl+C 给中断
        # 对中断敏感的操作应当放在这里
        assert self.version_meta

        # 将版本 json 等文件放回 ins_dir
        ins_dir = self.repository.versions.instance(self.spec.name)
        ins_dir.ensure_exists()

        # 链接主文件
        with self.repository.file_cacher.open(f'client-{self.spec.version}.jar') as file:
            link_file(file, ins_dir.main_file, 'symlink', force=True)

        write_model(ins_dir.mojang_meta_file, self.raw_version_meta)
        indexpath = self.repository.assets.index
        index_id = self.version_meta.dependencies.assets_index.id
        write_model(
            indexpath(index_id),
            self.raw_assets_index)

        write_model(
            ins_dir / f'{self.spec.name}.mpk',
            self.version_meta,
            encoder='msgpack')

        write_model(
            indexpath(index_id, ext='.mpk'),
            self.assets_index,
            encoder='msgpack')

        self.instance_dir = ins_dir
