import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import typer
from rich.box import ROUNDED
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.core.common.filesize import format_filesize
from app.core.i18n import tr
from app.core.minecraft.directories import Repository
from app.core.minecraft.instance_info import InstanceInfo, collect_instance_info
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.methods import find_repository


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


def _pair(label: str, value: str) -> tuple[Text, Text]:
    """构造一行「标签 - 值」"""
    return Text(label, style='dim'), Text(value)


def _grid(rows) -> Table:
    """把「标签 - 值」列表排成两列的网格"""
    table = Table.grid(padding=(0, 2), expand=False)
    table.add_column(justify='left', no_wrap=True)
    table.add_column(justify='left')

    for label, value in rows:
        table.add_row(label, value)

    return table


def _version_panel(info: InstanceInfo) -> Panel:
    """版本信息面板"""
    content = info.client_version

    rows = [
        _pair(tr("类型"), info.kind),
        _pair(tr("原版版本"), info.version or tr("未知")),
    ]

    if content is not None and content.pack_version is not None:
        pack = content.pack_version
        rows.append(_pair(
            tr("资源包格式"),
            str(pack.resource) if pack.resource is not None else tr("未知"),
        ))
        rows.append(_pair(
            tr("数据包格式"),
            str(pack.data) if pack.data is not None else tr("未知"),
        ))
    else:
        rows.append(_pair(tr("资源包 / 数据包格式"), tr("无法读取")))

    if content is not None:
        if content.protocol_version is not None:
            rows.append(_pair(tr("协议版本"), str(content.protocol_version)))

        if content.java_version is not None:
            rows.append(_pair(tr("Java 版本"), str(content.java_version)))

    return Panel(
        _grid(rows), title=tr("版本"), title_align='left', border_style='bright_cyan', expand=False
    )


def _content_panel(info: InstanceInfo, *, sized: bool = True) -> Panel:
    """内容统计面板"""
    content = info.content

    rows = [
        _pair(tr("占用空间"), format_filesize(info.size) if sized else tr("未统计")),
        _pair(tr("存档数量"), str(content.saves)),
        _pair(tr("资源包数量"), str(content.resourcepacks)),
        _pair(tr("光影包数量"), str(content.shaderpacks)),
        _pair(tr("模组数量"), str(content.mods)),
        _pair(tr("数据包数量"), str(content.datapacks)),
    ]

    return Panel(
        _grid(rows), title=tr("内容"), title_align='left', border_style='green', expand=False
    )


class ShowCommand(Command):
    name = 'show'

    async def main(
            self,
            name: str,
            *,
            repo: str | None = typer.Option(None, '-r', '--repo'),
            no_size: bool = typer.Option(False, '--no-size'),
    ):
        """
        显示单个实例的详细信息

        包括类型、版本号（原版与加载器）、占用空间、存档 / 资源包 / 光影包 / 模组 / 数据包
        的数量，以及从客户端 jar 中读取的资源包与数据包格式版本。

        :param name: 实例名称
        :param repo: 储存库名称或路径，默认为当前选中的储存库
        :param no_size: 不统计占用空间（大目录会明显变慢）
        """
        repository = _resolve_repository(repo)

        if not (instance := repository.versions.instance(name)).path.is_dir():
            console.error(tr("未找到名为 {} 的实例", name))
            raise typer.Abort()

        loop = asyncio.get_running_loop()

        # 统计占用空间需要遍历整个实例目录, 放到线程里避免阻塞
        with ThreadPoolExecutor(max_workers=1) as pool:
            with console.status(tr("正在收集实例信息...")):
                info = await loop.run_in_executor(
                    pool,
                    lambda: collect_instance_info(instance, compute_size=not no_size),
                )

        console.print(Panel(
            Group(
                Text(info.name, style='version'),
                Text(str(info.path), style='dim'),
            ),
            title=tr("实例"), title_align='left', border_style='bright_cyan',
        ))

        console.print(_version_panel(info))
        console.print(_content_panel(info, sized=not no_size))

        if info.notes:
            console.print(Group(*[
                Text(f'- {note}', style='dim')
                for note in info.notes
            ]))
