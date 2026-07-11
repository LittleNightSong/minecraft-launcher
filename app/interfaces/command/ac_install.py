import asyncio
import gc
import shutil
# import tracemalloc
from asyncio import TaskGroup
from concurrent.futures.thread import ThreadPoolExecutor
from itertools import chain
from pathlib import Path

import psutil
import rich.progress
import typer
from loguru import logger
from rich.columns import Columns
from rich.panel import Panel
from rich.progress import BarColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn, \
    DownloadColumn
from rich.text import Text

from app.core.common import ValidateResult, FileInfo, format_filesize, write_model
from app.core.common.file_validator import FileValidator, res_false_filter
from app.core.common.task import ProgressKind
from app.core.common.timer import SimpleStopWatch
from app.core.i18n import tr
from app.core.minecraft import VersionManifestModel, VersionMetaModel, AssetIndexModel
from app.core.minecraft.api import MinecraftAPI
from app.core.network import Session
from app.core.network.downloader import Downloader
from app.core.resources.base import rules_matcher
from app.core.resources.cache import CacheManager
from app.core.resources.repository import Repository
from app.implements.workers import LibrariesChecker, AssetsChecker
from app.implements.workers.common_files import CommonFileChecker
from app.interfaces.command.command import Command
from app.interfaces.command.common import typer_app, console
from app.core.minecraft.mc_version_lang import parse
from app.interfaces.command.methods import find_repo, call_and_cache, check_or_call
from app.interfaces.command.tty_task_viewer import TTYTaskViewer


def make_multi_shower(values, title, style='', border_style='none'):
    return Panel(
        title=title,
        style=style,
        border_style=border_style,
        renderable=Columns(
            values,
            expand=True, equal=True
        )
    )


# noinspection PyAttributeOutsideInit
class InstallCommand(Command, app=typer_app):
    name = 'install'

    async def process_single_version(
            self,
            url, version_id: str, localname: str
    ):

        version_meta = await call_and_cache(
            url=url,
            type=VersionMetaModel,
            name=tr("版本元数据文件 ({name})", name=version_id),
            cacher=self.cacher, key=f'versionmeta:{version_id}',
            echo=False, no_cache=self.no_cache
        )

        self.task_version_meta += 1  # 更新进度

        insdir = self.repo.versions.instance(localname)
        insdir.ensure_exists()

        write_model(insdir.meta_file, version_meta)

        # 提交依赖库文件列表
        await self.libs_checker.submit(version_meta.libraries)

        # 提交主文件
        await self.common_file_checker.submit(
            FileInfo.from_downloads_struct(
                downloads=version_meta.downloads.client,
                filename=insdir.main_file,
                meta=version_meta.downloads.client.url
            )
        )

        # 提交日志文件  # TODO
        # await self.commonfilechecker.submit(
        #     FileInfo.from_downloads_struct(
        #         downloads=version_meta.logging.client.file,
        #         filename=insdir
        #     )
        # )

        # 获取版本资源文件索引
        # .minecraft 文件夹的文件结构确定了有固定的地点存放 asset index
        # 所以不需要用 call_and_cache，直接本地校验即可
        asset_index = await check_or_call(
            url=version_meta.asset_index.url,
            type=AssetIndexModel,
            name=tr("版本资源文件索引 ({v_name}: \"{a_id}\")", v_name=version_id, a_id=version_meta.assets),

            local=self.repo.assets.indexes.fullpath(version_meta.assets),

            sha1=version_meta.asset_index.sha1,
            size=version_meta.asset_index.size,

            validator=self.file_validator,

            echo=False
        )

        self.task_asset_index += 1  # 更新进度

        # 提交索引
        await self.assets_checker.submit([
            (i.hash, i.size) for i in asset_index.objects.values()
        ])

    async def progress_selected_versions(self):
        self.viewer = TTYTaskViewer(console=console)
        # 首先创建 Libraries Checker 任务
        self.libs_checker = LibrariesChecker(
            env=rules_matcher.get_env(),
            libs_dir=self.repo.libraries,
            validator=self.file_validator
        ).start()

        self.assets_checker = AssetsChecker(
            assets_dir=self.repo.assets,
            validator=self.file_validator
        ).start()

        self.common_file_checker = CommonFileChecker(
            validator=self.file_validator
        ).start()

        # 创建用于进度回显的 TaskInfo，同时附加到 viewer 中
        self.task_version_meta = self.viewer.new_task(
            total=len(self.selected_versions),
            description=tr("获取版本描述文件"),
            progress_kind=ProgressKind.nom,
            running=True
        )
        self.task_asset_index = self.viewer.new_task(
            total=len(self.selected_versions),
            description=tr("获取资源索引"),
            progress_kind=ProgressKind.nom,
            running=True
        )

        self.viewer.title = tr("获取版本元数据文件")
        self.viewer.start()  # 启动回显器

        # 可以启动 process_single_version 了，这里的处理主要是获取安装所需要的所有文件信息
        async with TaskGroup() as tg:  # 并发处理所有选中的版本
            for selected in self.selected_versions:
                detail = selected['details']
                tg.create_task(
                    self.process_single_version(
                        detail.url, detail.id, localname=selected['name']
                    )
                )

        self.validated_libraries: list[ValidateResult] = await self.libs_checker
        self.validated_assets: list[ValidateResult] = await self.assets_checker
        self.validated_main_files: list[ValidateResult] = await self.common_file_checker

        self.viewer.stop()  # 停止回显

    @property
    def cacher(self) -> CacheManager:
        return self.repo.launcher_data.cache

    async def update_progress_bar(self, bar, id, total, tasks):
        while True:
            progress = 0

            for t in tasks:
                progress += t.progress

            # print(total, progress)

            bar.update(id, completed=progress, total=total)

            await asyncio.sleep(0.3)

    # ----------------------------------------------------------------------------------------------------
    async def init(self, repo, max_threads, max_connections, timeout, no_cache, **kwargs):
        self.repo: Repository = find_repo(repo, raise_for_unset=True)
        self.repo.ensure_exists()

        self.no_cache = no_cache

        self.thread_executor = ThreadPoolExecutor(max_threads)
        self.file_validator = FileValidator(executor=self.thread_executor)
        self.session = Session(timeout=timeout)
        self.minecraft_api = MinecraftAPI(self.session)

    async def cleanup(self, exc_type, exc_val, exc_tb):
        await self.session.close()
        self.thread_executor.shutdown()

    async def main(
            self,
            versions: list[str],
            repo: Path | None = typer.Option(None, '-r', "--repo"),  # 这些参数在 init 中被使用了
            max_threads: int = typer.Option((psutil.cpu_count() or 4), '-M', "--max-threads"),
            max_connections: int = typer.Option(64, '-m', "--max-connections"),
            timeout: int = typer.Option(60, '-t', '--timeout'),
            yes: bool = typer.Option(False, '-y', "--yes"),
            no_cache: bool = typer.Option(False, '-n', "--no-cache"),
    ):
        """
        安装版本
        """

        # 注入一个 logger output
        logger.add("debug.txt", level="DEBUG")

        parsed_versions = {v: parse(v) for v in versions}

        logger.info("已解析所有输入的版本信息 {}", parsed_versions)

        unparsed_versions = [
            k  # 我们只需要它的表示字符串
            for k, v in parsed_versions.items()

            if v is None or v.flags  # 目前启动器还不支持 flags
        ]

        if unparsed_versions:
            logger.error("发现无法解析的名称 {}", unparsed_versions)
            console.print(
                make_multi_shower(
                    unparsed_versions,
                    title=tr("发现下列无法解析的名称"),
                    style='red',
                    border_style='red'
                )
            )
            raise typer.Abort()

        del unparsed_versions

        manifest = await call_and_cache(
            url="https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
            type=VersionManifestModel,
            name=tr("版本清单"),
            cacher=self.cacher, key='versionmeta:manifest',
            echo=False, no_cache=no_cache
        )

        # 一次遍历找到所有选中的版本
        mapping = manifest.build_mapping()

        nonexistent_versions = []
        self.selected_versions = []

        for v in parsed_versions.values():
            if v.full_version.version not in mapping:
                nonexistent_versions.append(v.full_version)
            else:
                self.selected_versions.append({
                    'name': v.name or v.full_version.version,
                    'flags': v.flags,
                    'details': mapping[v.full_version.version],
                })

        if nonexistent_versions:
            logger.error(f"发现未知的版本 {nonexistent_versions}")
            console.print(Columns(
                nonexistent_versions,
                expand=True, equal=True, title=Text(tr("发现以下不存在的版本"), style='red')
            ))
            raise typer.Abort()

        # 找到和本地文件冲突的版本  # TODO: 我们应该先准确匹配，看看已安装的版本和现在想要安装的版本的信息是否一致，不一致再抛出这个错误
        if not yes and (conflics := [
            f"[bold]{selected['name']}[/bold][dim]({selected['details'].id})[/dim]"

            for selected in self.selected_versions
            if self.repo.versions.instance(selected['name']).is_vaild()
        ]):
            logger.error(f"发现与本地冲突的安装需求 {conflics}, {self.selected_versions}")
            console.print(make_multi_shower(
                conflics,
                title=tr("发现以下与本地名称冲突的安装需求"),
                style='red',
                border_style='red'
            ))
            console.print()
            console.error(
                f"{tr('也许这些实例并没有完整安装，如果想要覆盖和修复，请使用 [bold green]-y[/bold green] 参数')}")
            raise typer.Abort()  # TODO: 这里理应询问用户是否覆盖，但我们多版本选择起来有些困难

            # typer.confirm(tr("是否覆盖"))

        # 错误检查已经完成了
        # 可以开始真正的安装进程了

        with SimpleStopWatch() as sw:
            await self.progress_selected_versions()

        self.common_file_checker = None
        self.assets_checker = None
        self.libs_checker = None  # 清理资源

        console.print(
            tr(
                "[dim]在 {ms} ms 内分析了 {count} 个文件[/dim]",
                ms=sw.elapsed_time,
                count=sum(map(
                    len,
                    (self.validated_libraries, self.validated_assets, self.validated_main_files)
                ))
            ),
            '\n'  # 共两个换行
        )

        # 进行一次后处理，这次处理用于筛选真正需要下载的文件

        required_libs, required_assets, required_main_files = map(
            res_false_filter,
            (self.validated_libraries, self.validated_assets, self.validated_main_files)
        )

        del self.validated_libraries, self.validated_assets, self.validated_main_files  # 清理掉不在需要的数据

        if not (required_libs or required_assets or required_main_files):  # 啥也不需要
            console.print(tr("版本已正确安装，无需更新"))
            raise typer.Exit(0)

        # 随后输出更加详细的信息
        console.print(tr(
            "需要新下载 {} 个主文件, {} 个依赖库文件 以及 {} 个资源文件",
            len(required_main_files), len(required_libs), len(required_assets)))

        download_size = sum([
            r.file.size or 0  # 这里其实可以不需要 or 0
            for r in chain(required_libs, required_assets, required_main_files)
        ])
        disk_free_size = shutil.disk_usage(self.repo.path).free

        console.print()  # 一个换行

        console.print(tr(
            "预计下载大小：{}\n"
            "磁盘剩余空间：{}",
            format_filesize(download_size),
            format_filesize(disk_free_size)
        ))

        # 需要检查磁盘空间
        # disk_free_size = 0  # Test for code below

        if disk_free_size < download_size:
            console.error(
                tr("磁盘空间不足，安装被中断。"),
                tr("安装这些文件需要额外的 {}", format_filesize(download_size - disk_free_size)),
            )
            raise typer.Abort()

        del disk_free_size

        self.downloader = Downloader(
            session=self.session,
            max_connections=max_connections,
            executor=self.thread_executor
        )

        # 对所有文件都提交到下载器中
        tasks = []
        tasks.extend([
            self.downloader.create_task(
                url=self.minecraft_api.asset_url(vr.file.hash),
                filename=vr.file.filename
            )
            for vr in required_assets
        ])
        tasks.extend([
            self.downloader.create_task(
                url=self.minecraft_api.library_url_by_path(vr.file.meta),
                filename=vr.file.filename
            )
            for vr in required_libs
        ])
        tasks.extend([
            self.downloader.create_task(
                url=vr.file.meta,
                filename=vr.file.filename
            )
            for vr in required_main_files
        ])

        del required_main_files, required_assets, required_libs

        self.validated_assets = None
        self.validated_libraries = None
        self.validated_main_files = None

        self.viewer = None

        gc.collect()

        # await tqdm.gather(*[i.task for i in tasks])
        # await asyncio.gather(*[i.task for i in tasks])

        # 进度条是分离的，导致我们如果想要方便的整合数据只能靠轮询累计
        # 但。。。这真的不是什么好办法

        # debug

        with (
            rich.progress.Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as bar_download
        ):
            t_size = bar_download.add_task(tr("下载"))

            updator = asyncio.create_task(self.update_progress_bar(bar_download, t_size, download_size, tasks))

            async for task in asyncio.as_completed([i.task for i in tasks]):
                if task.exception():
                    raise task.exception()

            updator.cancel()

            bar_download.update(t_size, completed=download_size)  # 保证进度条到最后是完整的

        console.print(tr("[green]安装完成[/green]"))
        # console.print(tracemalloc.get_traced_memory())
