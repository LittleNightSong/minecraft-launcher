from pathlib import Path

import typer
from rich.box import ROUNDED
from rich.table import Table
from rich.text import Text

from app.core.i18n import tr
from app.core.minecraft.directories import Repository
from app.core.minecraft.instance_metadata import FixResult, FixStatus, fix_instance
from app.core.network import Session
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.methods import find_repository

# 状态对应的颜色与文本
_STATUS_STYLES = {
    FixStatus.FIXED: ('green', "已修复"),
    FixStatus.SKIPPED: ('dim', "跳过"),
    FixStatus.FAILED: ('red', "失败"),
}


def _resolve_repository(repo: str | None) -> Repository:
    """
    解析储存库

    与其它命令一致, 允许直接指向一个包含 ``.minecraft`` 文件夹的目录。
    """
    minecraft = find_repository(repo)

    if minecraft is None:
        console.error(tr("未指定本地储存库或指定的存储库无效"))
        raise typer.Abort()

    if not minecraft.versions.path.is_dir() and (minecraft.path / '.minecraft' / 'versions').is_dir():
        minecraft = Repository(minecraft.path / '.minecraft')

    if not minecraft.versions.path.is_dir():
        console.error(tr("该储存库中没有任何版本：{}", minecraft.path))
        raise typer.Abort()

    return minecraft


class FixInstanceMetadataCommand(Command):
    name = 'fix-instance-metadata'

    async def main(
            self,
            *,
            repo: str | None = typer.Option(None, '-r', '--repo'),
            data_dir: Path | None = typer.Option(None, '-d', '--data-dir'),
            online: bool = typer.Option(False, '--online'),
            force: bool = typer.Option(False, '-f', '--force'),
            yes: bool = typer.Option(False, '-y', '--yes'),
    ):
        """
        为缺少描述文件（.mpk）的实例，根据其版本描述文件（.json）生成描述文件

        会自动推断原版版本号、加载器与加载器版本号，以及客户端主文件。
        推断全部基于本地信息，不会联网；推断不出原版版本号的实例会被跳过，
        以免写入错误的版本信息（它决定资源索引与 Java 版本）。

        :param repo: 储存库名称或路径，默认为当前选中的储存库
        :param data_dir: 原启动器的数据目录，用于在其中查找客户端主文件
        :param online: 允许联网比对 Mojang 版本清单来推断原版版本号（较慢，默认关闭）
        :param force: 覆盖已经存在的描述文件
        :param yes: 跳过确认
        """
        repository = _resolve_repository(repo)

        data_dir_path = data_dir
        if data_dir_path is None and repository.path.name != '.minecraft':
            # 浏览器下载得到的仓库常常是 <数据目录>/.minecraft, 此时主文件在旁边
            candidate = repository.path / '.minecraft'
            if candidate.is_dir():
                data_dir_path = candidate

        instances = repository.versions.instances(skip_broken=False)

        if not instances:
            console.print(tr("该储存库中没有任何实例"))
            return

        # 只处理缺少描述文件的实例; --force 时处理全部
        pending = [
            i for i in instances
            if force or not i.is_valid()
        ]

        if not pending:
            console.print(tr("所有实例都已经有描述文件，无需修复"))
            return

        already = len(instances) - len(pending)

        console.print(tr(
            "将对 [repr.number]{}[/] 个实例生成描述文件",
            len(pending)
        ) + (
            tr("（另有 {} 个实例已有描述文件，将被跳过）", already)
            if already else ''
        ))

        if online:
            console.print(tr("[dim]已启用联网推断，可能会持续较长时间，按 Ctrl+C 可中断[/dim]"))

        console.print()

        results: list[FixResult] = []

        # 整批实例共享会话与推断缓存, 联网时不会对同一个版本重复请求
        session = Session() if online else None
        cache: dict = {}

        try:
            with console.status(tr("正在生成描述文件...")):
                for instance in pending:
                    result = await fix_instance(
                        instance,
                        name=instance.name,
                        data_dir=data_dir_path,
                        online=online,
                        force=force,
                        session=session,
                        cache=cache,
                    )
                    results.append(result)
        finally:
            if session is not None:
                await session.close()

        _show_results(results, total=len(pending))

        failed = [r for r in results if r.status == FixStatus.FAILED]

        if failed:
            console.print(tr("[yellow]有 {} 个实例未能生成描述文件[/]", len(failed)))
            raise typer.Exit(code=1)


def _show_results(results: list[FixResult], *, total: int):
    """以表格形式展示修复结果"""
    table = Table(
        tr("实例"),
        tr("状态"),
        tr("版本"),
        tr("加载器"),
        tr("说明"),
        header_style="bold green",
        box=ROUNDED,
        expand=True,
    )

    for result in results:
        style, status_text = _STATUS_STYLES[result.status]

        loader = result.loader or '-'
        if result.loader and result.loader_version:
            loader = f'{result.loader} {result.loader_version}'

        details = [*(result.notes if result.status != FixStatus.FAILED else []), *([result.error] if result.error else [])]

        table.add_row(
            Text(result.name),
            Text(status_text, style=style),
            Text(result.version or '-'),
            Text(loader),
            Text('；'.join(details) or '-', style='dim'),
        )

    console.print(table)

    fixed = sum(1 for r in results if r.status == FixStatus.FIXED)
    skipped = sum(1 for r in results if r.status == FixStatus.SKIPPED)
    failed = sum(1 for r in results if r.status == FixStatus.FAILED)

    console.print(tr(
        "完成：成功 [green]{}[/]，跳过 [dim]{}[/]，失败 [red]{}[/]（共 {}）",
        fixed, skipped, failed, total
    ))
