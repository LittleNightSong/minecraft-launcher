import asyncio
import shutil
# import tracemalloc
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import asyncstdlib
import psutil
import typer
from loguru import logger
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, TransferSpeedColumn, FileSizeColumn, \
    TotalFileSizeColumn, DownloadColumn

from app.core.common import format_filesize, FormattedExceptionBase, accept_errors
from app.core.fetcher import Fetcher
from app.core.file_validator import FileValidator
from app.core.i18n import tr
from app.core.minecraft import VersionManifestModel
from app.core.minecraft.resources import Repository
from app.core.models import FileSpec
from app.core.models.env import Environment
from app.core.models.version_spec import VersionSpec
from app.core.network import Session
from app.core.network.downloader import Downloader
from app.core.third_party.mojang import MinecraftAPI
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.methods import find_repository, call_and_cache
from app.interfaces.commandline.base.tty_task_viewer import TTYTaskViewer
from .install_guide import VersionSelectorApp
from .installers import BaseInstaller
from .installers.base_installer import Reasons
from .installers.vanilla_installer import VanillaInstaller


async def update_progress_bar(bar, id, tasks, total):
    while True:
        progress = 0

        for t in tasks:
            progress += t.progress

        # print(total, progress)

        if progress != 0:
            bar.update(id, completed=progress)
            # bar.refresh()
        else:
            bar.update(id, total=None, completed=None)
            # bar.refresh()

        await asyncio.sleep(0.1)


# noinspection PyAttributeOutsideInit
class InstallCommand(Command):
    name = 'install'

    installers: list[type[BaseInstaller]] = [
        VanillaInstaller
    ]

    async def start_install_guide(self):
        """启动交互式安装向导"""
        # 获取版本清单
        manifest = await call_and_cache(
            url=self.minecraft_api.url_version_manifest,
            type=VersionManifestModel,
            name=tr("版本清单"),
            cacher=self.cacher,
            key='versionmeta:manifest',
            no_cache=self.no_cache,
            echo=True
        )

        # 运行 Textual 应用
        app = VersionSelectorApp(manifest)
        selects = await app.run_async()

        if not selects:
            console.print(tr("未选择任何版本，安装取消"))
            raise typer.Abort()

        # 返回选中的版本 ID 列表（字符串列表）
        return [
            i.version
            for i in selects
        ]

    # ----------------------------------------------------------------------------------------------------
    async def init(self, repository, max_threads, timeout):
        self.repo: Repository = find_repository(repository, abort=True)
        self.repo.ensure_exists()

        self.cacher = self.repo.launcher_data.model_cacher
        self.file_cacher = self.repo.launcher_data.file_cacher


        self.thread_executor = ThreadPoolExecutor(max_threads)
        self.file_validator = FileValidator(executor=self.thread_executor)
        self.session = Session(timeout=timeout)
        self.minecraft_api = MinecraftAPI(self.session)
        self.fetcher = Fetcher(self.session, self.cacher, self.file_cacher, self.file_validator)

    async def cleanup(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and issubclass(exc_type, FormattedExceptionBase):
            console.error(str(exc_val))

            with accept_errors(AttributeError):
                await self.session.close()
                self.thread_executor.shutdown()

            return True  # 吞掉异常

        with accept_errors(AttributeError):
            await self.session.close()
            self.thread_executor.shutdown()

    # async def validate_file(self, filename_or_key, spec: FileSpec, in_file_cache=False):
    #     if not in_file_cache:
    #         return await self.file_validator.validate(
    #             filename_or_key, spec
    #         )
    #     else:
    #         with self.file_cacher.open(filename=filename_or_key) as f:
    #             return await self.file_validator.validate(
    #                 filename_or_key,
    #                 FileSpec(
    #                     checksum=spec.checksum,
    #                     algorithm=spec.algorithm,
    #                     last_modified=spec.last_modified,
    #                     meta=spec
    #                 )
    #             )

    async def main(
            self,
            version: str,
            *,
            name: str | None = None,
            loader: Literal['forge', 'neoforge', 'fabric'] | None = None,
            loader_version: str | None = None,

            repository: Path | None = typer.Option(None, '-r', "--repository"),
            max_threads: int = typer.Option((psutil.cpu_count() or 4), '-M', "--max-threads"),
            max_connections: int = typer.Option(64, '-m', "--max-connections"),
            timeout: int = typer.Option(60, '-t', '--timeout'),
            yes: bool = typer.Option(False, '-y', "--yes"),
    ):
        """
        安装版本
        """

        # 构建 VersionSpec
        spec = VersionSpec(
            name=name,
            version=version,
            loader=loader,
            loader_version=loader_version,
            repository=self.repo
        )

        # 尝试发现 installer

        installer = None
        for candidate in self.installers:
            installer = await candidate.get_installer(
                spec, self.session, self.fetcher, Environment.new()
            )

            if installer is not None:
                break

        if installer is None:
            console.error(tr("无法为请求安装的版本匹配安装器，请检查您的配置信息"))
            return

        with console.status(tr("获取元数据...")) as s, TTYTaskViewer(console) as viewer:
            await installer.fetch()

            s.update(tr("分析元数据文件..."))
            required_files = [item async for item in installer.collect()]

            s.update(tr("校验本地文件[yellow]...[/]"))

            tasks = [
                self.file_validator.validate(filename, fspec)
                for filename, fspec in required_files
            ]

            results = [await i async for i in console.async_trace(
                asyncio.as_completed(tasks),
                tr("正在校验："),
                total=len(tasks)
            )]
            # print(results)

            downloads = [i async for i in installer.analyze(results)]

            if downloads:
                # 开始下载
                s.update(tr("正在准备资源..."))

                downloader = Downloader(max_connections, self.thread_executor, self.file_cacher, self.session)

                total_size = 0
                for i in downloads:
                    if i.estimated_size and i.estimated_size > 0:  # 这里不去判定是否是 None，因为 0 和 None 没有区别，都可以舍弃
                        total_size += i.estimated_size

                # 检查磁盘
                available = shutil.disk_usage(spec.repository).free

                console.print(tr(
                    "将要下载 {} 个文件\n"
                    "磁盘剩余空间：{}\n"
                    "安装预计需要：{}\n",
                    len(tasks),
                    format_filesize(available),
                    format_filesize(total_size)
                ))

                if available < total_size:
                    logger.error("磁盘空间不足，安装取消")
                    console.error(tr("磁盘空间不足，安装取消"))
                    await installer.on_interrupt('analyze', Reasons.DISK_SPACE_INSUFFICIENT)
                    return

                console.confirm(tr("安装？"), skip=yes, abort=True)

                tasks = [downloader.create_task(i) for i in downloads]

                s.update(tr("[bold]正在下载资源[/][yellow]...[/]"))
                with Progress(
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TransferSpeedColumn(),
                        DownloadColumn(),
                        TimeRemainingColumn(),
                        console=console,
                        refresh_per_second=5
                        # auto_refresh=False,
                ) as pr:
                    main_task = pr.add_task(tr("下载"), total=total_size)
                    update_task = asyncio.create_task(update_progress_bar(pr, main_task, tasks))

                    async_tasks = [i.task for i in tasks]
                    async for cnt, i in asyncstdlib.enumerate(asyncio.as_completed(async_tasks)):
                        if i.exception() is not None:
                            logger.opt(exception=i.exception()).error("下载过程中的异常")
                            console.error(tr("下载过程中发生异常：{}", i.exception()))
                            # 清理资源
                            for a in async_tasks:
                                if a.done():
                                    if a.exception() is not None:
                                        logger.opt(exception=a.exception())
                                else:
                                    a.cancel()
                            break

                        s.update(tr("[bold]正在准备资源[/][yellow]...[/] ({} / {})", cnt, len(async_tasks)))

                    update_task.cancel()
                    pr.update(main_task, completed=total_size)
            else:
                console.print(tr("[yellow bold]版本已正确安装[/]"))

            s.update(tr("正在执行额外的安装后步骤..."))
            await installer.post_install()
            console.print(tr("[yellow bold]完成[/]"))
