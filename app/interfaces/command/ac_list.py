import builtins
import os
from typing import Literal

import rich.table
import typer
from rich.columns import Columns

from app.common.concurrent_ import as_sync
from app.i18n.translator import trs, tr
from app.interfaces.command.ac_install import find_repo
from app.interfaces.command.common import typer_app, console, session
from app.interfaces.command.methods import get_version_manifest
from app.resources.instance import InstanceDirectory
from app.resources.repository import Repository


def split_list(lst, n):
    """
    将列表平分成 n 份

    Args:
        lst: 要分割的列表
        n: 分割的份数

    Returns:
        包含 n 个子列表的列表
    """
    if n <= 0:
        raise ValueError("份数必须大于0")

    k, m = divmod(len(lst), n)
    return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]


def new_table():
    return rich.table.Table(*trs("版本", "名称", "位置"))


@typer_app.command()
@as_sync
async def list(
        *,
        online: bool = False,
        repo: str | None = typer.Option(None, '-r', '--repo'),
        tables: int | None = typer.Option(2, '-t', "--tables"),
        type: Literal['release', 'snapshot', 'all'] = typer.Option('release', '-T', "--type")
):
    repo = find_repo(repo)
    mapping = None
    minecraft = None

    if repo is not None:
        minecraft = Repository(repo)
        mapping = minecraft.versions.mapping

    info_list = []

    if online:
        async with session:
            manifest = await get_version_manifest()

        versions = manifest['versions']
        for ver in versions:
            id = ver['id']

            if type != 'all' and type != ver['type']:
                continue

            version = id

            if mapping and (local_versions := mapping.get(version)):
                local_ver: InstanceDirectory
                for local_ver in local_versions:
                    info_list.append((
                        version,
                        local_ver.name,
                        os.sep + local_ver.path.relative_to(minecraft.path).__fspath__()
                    ))
                    version = ''
            else:
                info_list.append((version, tr("[green] 可下载 [/green]"), None))

    else:
        if repo is None:
            console.print(tr("[red]未指定本地储存库位置，无法列出版本[/red]"))
            console.print(tr("[red]如果你想在线浏览版本列表，可以加上[blue] --online [/blue]标志"))
            raise typer.Abort()

        for version, instances in reversed(minecraft.versions.mapping.items()):
            _ = iter(instances)
            ins = next(_)
            info_list.append((version, ins.name, ins.path.relative_to(minecraft.path).__fspath__()))
            for ins in _:
                info_list.append(('', ins.name, ins.path.relative_to(minecraft.path).__fspath__()))

    if info_list:
        lists = split_list(info_list, tables)

        # console.print(lists)

        # 转换成 Table
        def convert(x):
            t = new_table()
            [t.add_row(*row) for row in x]
            return t

        tables = builtins.map(convert, lists)
        console.print(Columns(tables, padding=(0, 4)))
    else:
        console.print(tr("没有安装的版本"))
