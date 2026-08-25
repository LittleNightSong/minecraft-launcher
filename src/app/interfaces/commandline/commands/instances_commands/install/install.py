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
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, TransferSpeedColumn, DownloadColumn
from rich.status import Status

from app.core.common import format_filesize, FormattedExceptionBase, accept_errors
from app.core.fetcher import Fetcher
from app.core.file_validator import FileValidator
from app.core.i18n import tr
from app.core.minecraft.directories import Repository
from app.core.models.env import Environment
from app.core.models.version_spec import VersionSpec
from app.core.network import Session
from app.core.network.downloader import Downloader
from app.impls.installers import BaseInstaller
from app.impls.installers.base_installer import Reasons, InstallContext
from app.impls.installers.fabric_installer import FabricInstaller
from app.impls.installers.neoforge_installer import NeoForgeInstaller
from app.impls.installers.runner import InstallerRunner
from app.impls.installers.vanilla_installer import VanillaInstaller
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console, MyConsole
from app.interfaces.commandline.base.methods import find_repository
from app.third_party.mojang import MinecraftAPI


class CommandLineInteractor:
    actor_id = 'commandline'

    def __init__(self, console: MyConsole, status_obj: Status, verbose=False, prefix=''):
        self.console = console
        self.status_obj = status_obj
        self.verbose = verbose
        self.prefix = prefix

    def status(self, text=None):
        if text is None:
            self.status_obj.stop()

        else:
            self.status_obj.start()
            self.status_obj.update(text)

    def print(self, text):
        self.console.print(self.prefix, text)

    def log(self, text):
        if self.verbose:
            self.console.print(self.prefix, text)


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
        VanillaInstaller, FabricInstaller, NeoForgeInstaller
    ]

    # ----------------------------------------------------------------------------------------------------
    async def init(self, repository, max_threads, timeout):
        self.repository: Repository = find_repository(repository, abort=True)
        self.repository.ensure_exists()

        self.cacher = self.repository.launcher_data.model_cacher
        self.file_cacher = self.repository.launcher_data.file_cacher

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
        )

        with (
            console.status(tr("正在获取元数据...")) as s,
            console.status('Installer Processing...') as si,  # 这个 status 是给 interactor 用的
        ):

            # 尝试发现 installer
            installer = None
            install_context = InstallContext(
                spec=spec,
                repository=self.repository,
                session=self.session,
                file_validator=self.file_validator,
                fetcher=self.fetcher,
                env=Environment.new(),
                interactor=CommandLineInteractor(console, si)
            )

            for candidate in self.installers:
                installer = await candidate.get_installer(install_context)

                if installer is not None:
                    break

            if installer is None:
                console.error(tr("无法为请求安装的版本匹配安装器，请检查您的配置信息"))
                return

            runner = InstallerRunner(
                installer,
                install_context
            )

            await runner.fetch()

            console.print(tr("新的版本名为 {!r}", spec.name))
            ins_dir = self.repository.instance(spec.name)
            if ins_dir.is_valid():
                version_meta = ins_dir.version_meta
                # 尝试比较两个 spec
                local = (version_meta.version, version_meta.loader, version_meta.loader_version)
                will = (spec.version, spec.loader, spec.loader_version)

                if local != will:
                    console.warning(tr("本地已存在名为 {} 的版本", spec.name))
                    console.print(tr("  - 主版本号：[bold]{}[/]", version_meta.version))
                    console.print(tr("  - 加载器：[bold]{}[/]", version_meta.loader or tr("无")))
                    console.print(tr("  - 加载器版本号：[bold]{}[/]", version_meta.loader_version or tr("无")))
                    console.print('\n')
                    console.confirm(tr("继续操作可能会破坏已有的版本文件，是否继续？"), skip=yes, abort=True)

            s.update(tr("分析元数据文件..."))
            await runner.collect()

            s.update(tr("校验本地文件[yellow]...[/]"))

            sync_generator, n_tasks = runner.validate()  # 获取校验任务的即时生成器和数量
            async for _ in console.aprogress(  # 手动驱动校验任务，同时显示进度
                    sync_generator,
                    tr("正在校验"),
                    total=n_tasks
            ): ...

            # print(results)
            # console.print(res_false_filter(await asyncio.gather(*runner.validate_tasks)))

            await runner.analyze()

            downloads = runner.download_plans

            if downloads:
                # 开始下载
                s.update(tr("正在准备资源..."))

                total_size = 0  # 这里估算下载的总大小
                for i in downloads:
                    if i.estimated_size and i.estimated_size > 0:  # 这里不去判定是否是 None，因为 0 和 None 没有区别，都可以舍弃
                        total_size += i.estimated_size

                # 检查磁盘剩余空间
                available = shutil.disk_usage(install_context.repository).free

                console.print(tr(
                    "将要下载 {} 个文件\n"
                    "磁盘剩余空间：{}\n"
                    "安装预计需要：{}\n",
                    len(downloads),
                    format_filesize(available),
                    format_filesize(total_size)
                ))

                if available < total_size:
                    logger.error("磁盘空间不足，安装取消")
                    console.error(tr("磁盘空间不足，安装取消"))
                    await runner.interrupt(Reasons.DISK_SPACE_INSUFFICIENT)
                    return

                console.confirm(tr("安装？"), skip=yes, abort=True)

                downloader = Downloader(
                    max_connections,
                    self.thread_executor,
                    self.file_cacher,
                    self.session
                )

                tasks = runner.start_download(downloader)

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
                    update_task = asyncio.create_task(update_progress_bar(pr, main_task, tasks, total_size))

                    async_tasks = [i.task for i in tasks if i.task]

                    async for cnt, i in asyncstdlib.enumerate(asyncio.as_completed(async_tasks)):
                        if i.exception() is not None:
                            s.stop()
                            logger.opt(exception=i.exception()).error("下载过程中的异常")
                            console.error(tr("下载过程中发生异常：{}", i.exception()))
                            # 清理资源
                            for a in async_tasks:
                                if a.done():
                                    if a.exception() is not None:
                                        logger.opt(exception=a.exception())
                                else:
                                    a.cancel()

                            await runner.interrupt(Reasons.NETWORK_ERROR)
                            return

                        s.update(tr("[bold]正在准备资源[/][yellow]...[/] ({} / {})", cnt, len(async_tasks)))

                    update_task.cancel()
                    pr.update(main_task, completed=total_size)
            else:
                console.confirm(tr("无需下载任何文件。继续安装？"), skip=yes, abort=True)

            s.update(tr("正在处理下载数据..."))
            await installer.post_download(downloads)

            s.update(tr("正在执行自定义安装..."))
            with console.no_interrupt():
                await installer.post_install()

            console.print(tr("[yellow bold]安装已完成[/]"))
