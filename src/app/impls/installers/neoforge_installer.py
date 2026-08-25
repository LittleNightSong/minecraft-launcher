import asyncio
import os.path
from datetime import datetime
from pathlib import Path
from typing import Self, AsyncIterable, Literal
from urllib.parse import urljoin

import msgspec
from loguru import logger

from app.core.common import update_attrs
from app.core.configs import cfg
from app.core.files.jar import JarFile
from app.core.minecraft import MinecraftVersion
from app.core.models import FileSpec
from app.core.models.methods import unify
from app.core.network.downloader import HTTPDownloadPlan
from app.core.process_builder import ProcessBuilder
from app.core.remotezip import RemoteZip
from app.third_party.mojang.models.version_meta import StandardLibraryStruct
from app.third_party.neoforge_maven import NeoForgeMavenAPI
from .base_installer import InstallContext, ValidateRequest, LocalFileValidateRequest
from .vanilla_installer import VanillaInstaller
from ...core.i18n import tr
from ...core.osio import AsyncOSFile


def f(__message, *args, **kwargs):
    return str(__message).format(*args, **kwargs)


class LazyRemoteZip:
    rz: RemoteZip

    def __init__(self, rz):
        self.rz = rz
        self.inited = False

    async def load_initial_data(self):
        if self.inited:
            return

        await self.rz.fetch_zip_info()
        await self.rz.fetch_file_list()
        self.rz.build_mapping()
        self.inited = True

    async def load_single_file(self, filename: bytes):
        await self.load_initial_data()
        return await self.rz.load_single_file(filename)

    async def stream_single_file(self, filename: bytes):
        await self.load_initial_data()
        async for i in self.rz.stream_single_file(filename):
            yield i

    async def download_single_file(self, filename: bytes, target: str | bytes | Path):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        async with AsyncOSFile.open(target, os.O_WRONLY | os.O_BINARY | os.O_CREAT | os.O_TRUNC) as f:
            async for chunk in self.stream_single_file(filename):
                await f.write(chunk)


class NeoForgeInstaller(VanillaInstaller):
    prefix = 'neoforge'


    @classmethod
    async def get_installer(cls, context: InstallContext) -> Self | None:
        if context.spec.loader == 'neoforge':
            return cls(context)
        return None

    def __init__(self, context: InstallContext):
        super().__init__(context)
        self.nf_rz: LazyRemoteZip | None = None
        self.nf_api = NeoForgeMavenAPI(self.session)
        self.nf_profile = None
        self.nf_java = None

    async def fetch(self):
        has_name = self.spec.name is not None

        await super().fetch()

        # NeoForge 安装需要 java 坏境
        # 提前检查 java 问题
        assert self.version_meta
        javas = cfg.get_javas_forward(self.version_meta.dependencies.java.major)
        if not javas:
            raise RuntimeError()

        for java in javas:
            if os.path.exists(java.path):
                break
        else:
            raise RuntimeError()

        self.nf_java = java

        self.interactor.log(
            f("选中执行器 Java: JAVA {} at {!r}", self.nf_java.major, self.nf_java.path))

        # 首先获取元数据列表
        self.interactor.status(tr("拉取 NeoForge 元数据"))

        metadata = await self.nf_api.fetch_metadata()
        logger.info('\n{}:\n{}', "NeoForge 版本列表", '\t\n'.join(
            f'- {_}' for _ in metadata.sorted_versions
        ))

        loader_ver = self.spec.loader_version

        mc_version = MinecraftVersion(self.version_meta.version)
        if loader_ver is None:
            for i in metadata.sorted_versions:
                if i.mc_version != mc_version:
                    self.interactor.log(f("版本 {} 与当前游戏版本不兼容，已跳过", self.spec.version))
                    continue

                if i.release is None:
                    self.interactor.log(f("已选中稳定版 {}", i.version))
                    loader_ver = i.version
                    break
                else:
                    self.interactor.log(f("版本 {} 非正式版，已跳过", i.version))
            else:
                self.interactor.log("无法找到与该游戏版本兼容的 NeoForge")
                self.interactor.print(tr("无法找到合适的 NeoForge 版本，也许是因为你选择的游戏版本不支持 NeoForge"))
                self.interactor.print(tr("NeoForge 版本要求：1.20.2+，不包括某些愚人节版本"))
                raise RuntimeError("无法找到合适的 NeoForge 版本")

        else:
            assert loader_ver in metadata.versions

        self.interactor.print(tr("选中 NeoForge 版本：{}", loader_ver))

        rz = LazyRemoteZip(RemoteZip(self.nf_api.get_installer_url(loader_ver), self.session))

        # self.interactor.print(tr("拉取包信息成功"))

        # self.interactor.print(tr("准备提取文件 （方式：LazyRemoteZip）"))
        self.interactor.status(tr("提取所需文件... (install_profile.json)"))

        async def _():
            return msgspec.json.decode(
                await rz.load_single_file(b'install_profile.json')
            )

        raw_profile = await self.fetcher.fetch_model_into_pool(
            key=f'neoforge-{loader_ver}-profile.json',
            fetcher=_,
        )
        profile = msgspec.convert(raw_profile, type=self.nf_api.models.NeoForgeInstallProfile)

        async def _():
            return msgspec.json.decode(
                await rz.load_single_file(profile.json.removeprefix('/').encode()),
            )

        self.interactor.status(tr("提取所需文件... (patched version.json)"))
        nf_versionmeta = await self.fetcher.fetch_model_into_pool(
            key=f'neoforge-{loader_ver}-version.json',
            fetcher=_
        )
        # self.interactor.print(tr("提取文件成功"))
        self.interactor.status(tr("合并版本元数据"))
        # ------------------------------------ 数据合并
        # 合并 libraries
        assert self.version_meta
        assert self.raw_version_meta

        self.version_meta.dependencies.libraries.extend(
            unify(i, StandardLibraryStruct) for i in
            nf_versionmeta['libraries']
        )

        # 合并启动参数
        arg = unify(nf_versionmeta['arguments'], self.api.models.version_meta.ArgumentsStruct)
        self.version_meta.arguments.game.extend(arg.game)
        self.version_meta.arguments.jvm.extend(arg.jvm)

        # 覆盖主类等信息
        #   "releaseTime": "2026-08-11T23:48:28.835789343",
        #   "mainClass": "net.neoforged.fml.startup.Client",
        # 以及加载器相关的信息
        # loader, loader_version
        update_attrs(
            self.version_meta,

            main_class=nf_versionmeta['mainClass'],
            release_time=msgspec.convert(nf_versionmeta['releaseTime'], datetime),
            loader='neoforge',
            loader_version=loader_ver
        )

        # 合并原版 json
        self.raw_version_meta['libraries'].extend(nf_versionmeta['libraries'])
        self.raw_version_meta['arguments']['game'].extend(nf_versionmeta['arguments']['game'])
        self.raw_version_meta['arguments']['jvm'].extend(nf_versionmeta['arguments']['jvm'])

        self.raw_version_meta['mainClass'] = nf_versionmeta['mainClass']
        self.raw_version_meta['time'] = nf_versionmeta['time']
        self.raw_version_meta['releaseTime'] = nf_versionmeta['releaseTime']

        # NeoForge 补丁已完成一半

        self.nf_profile = profile

        if not has_name:
            self.spec.name = f'{self.version_meta.version}-neoforge-{loader_ver}'

        self.interactor.status()  # 清除状态
        self.nf_rz = rz

        self.spec.loader = 'neoforge'
        self.spec.loader_version = loader_ver

    async def collect(self) -> AsyncIterable[ValidateRequest]:
        async for i in super().collect():
            yield i

        T = self.nf_api.models.NeoForgeInstallProfile
        # pyrefly: ignore [bad-assignment]
        profile: T = self.nf_profile
        repo = self.repository
        env = self.env

        for lib in profile.libraries:
            lib = lib.unify()
            for f in lib.collect(env):
                filename = repo.librarypath(f.name).__fspath__()
                yield LocalFileValidateRequest(
                    filename=filename,
                    spec=FileSpec(
                        size=f.size,
                        checksum=f.sha1
                    ),
                    group='neoforge-installer',
                    extra=HTTPDownloadPlan(
                        url=urljoin(f.maven_url, str(f.path).removeprefix('/')),
                        target=filename,
                        estimated_size=f.size
                    )
                )

    async def pre_download(self, result) -> AsyncIterable[HTTPDownloadPlan]:
        async for i in super().pre_download(result):
            yield i

        for i in result.get_responses(group='neoforge-installer'):
            if not i.ok and isinstance(i.extra, HTTPDownloadPlan):
                yield i.extra

    async def post_download(self, download_plans: list[HTTPDownloadPlan]):
        assert self.nf_rz

        repo = self.repository
        rz = self.nf_rz

        files = []
        for v in self.nf_profile.data.values():
            if v.startswith('/'):
                files.append(v[1:])

        self.interactor.status(tr("下载 NeoForge 数据文件"))
        with repo.file_cacher.use(f'neoforge-{self.version_meta.loader_version}-data') as data_dir:
            async def download_one(file: str):
                filename = data_dir / file
                if filename.exists():
                    return
                await rz.download_single_file(file.encode(), filename)

            tasks = [
                asyncio.create_task(download_one(f))
                for f in files
            ]

            await asyncio.gather(*tasks)

    async def post_install(self):
        assert self.nf_java
        assert self.nf_rz
        assert self.version_meta

        rz: LazyRemoteZip = self.nf_rz
        repo = self.repository

        with (
            repo.file_cacher.open(f'client-{self.version_meta.version}.jar', cleanup_on_error=False) as minecraft_jar,
        ):
            T = self.nf_api.models.NeoForgeInstallProfile
            # pyrefly: ignore [bad-assignment]
            profile: T = self.nf_profile

            side: Literal['client', 'server'] = 'client'
            with repo.file_cacher.use(f'neoforge-{self.version_meta.loader_version}-data') as dir:
                def auto_cast(value: str):
                    if value[0] == '[' and value[-1] == ']':
                        return repo.librarypath(value[1:-1]).__fspath__()
                    elif value.startswith('/'):
                        return (dir / value[1:]).__fspath__()
                    else:
                        return value

                data = {
                    k: auto_cast(getattr(v, side))
                    for k, v in profile.data.items()
                }
                data.update({
                    'ROOT': repo.path.__fspath__(),
                    'SIDE': side,
                    'MINECRAFT_JAR': minecraft_jar
                })

            for processor in profile.processors:
                if side not in processor.sides:
                    continue

                exe_name = 'javaw.exe' if os.name == 'nt' else 'javaw'
                sep = ';' if os.name == 'nt' else ':'

                builder = ProcessBuilder()
                builder <<= Path(self.nf_java.path) / exe_name

                builder += [
                    '-cp', sep.join([
                        repo.librarypath(i).__fspath__()
                        for i in processor.classpath
                    ]),
                ]

                with JarFile(repo.librarypath(processor.jar)) as f:
                    main_class = f.main_class

                builder += main_class
                builder += [
                    auto_cast(i.format(**data))
                    for i in processor.args
                ]

                ps = await builder.run()
                stdout, stderr = await ps.communicate()

                if ps.returncode != 0:
                    logger.error("执行处理器（{}）失败", processor.jar)
                    logger.error("Java 进程输出：\nstdout:\n{}\nstderr:\n{}", stdout, stderr)
                    raise RuntimeError(f'Failed to execute processor')

        await super().post_install()
