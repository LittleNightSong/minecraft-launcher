from pathlib import Path

import rich.box
import typer
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from app.core.configs import cfg
from app.core.i18n import tr
from app.core.minecraft import Repository
from app.interfaces.commandline.base import CommandGroup, console


class RepositoryCommands(CommandGroup):
    name = 'repository'
    commands = ['add', 'show', 'remove',  'list']

    async def add(
            self,
            name: str, path: Path,
            select: bool = typer.Option(False, '-s', '--select'),
            yes: bool = typer.Option(False, '-y', '--yes')
    ):
        path = path.absolute()
        if cfg.exists_repository(name):
            repo = cfg.get_repository(name)
            console.confirm(
                tr(
                    "已存在名称为 [bold]{}[/bold] ([not highlight][green]{}[/green][/not highlight]) 的储存库，是否覆盖？",
                    name, repo.path
                )
                , abort=True, skip=yes
            )

        with console.no_interrupt():
            cfg.add_repository(name, path)

            if select:
                cfg.set_selected_repository(name)

    async def show(self, name: str | None = None):
        try:
            if name is None:
                repo = cfg.get_selected_repository()

                if repo is None:
                    console.error(tr("未选中任何储存库"))
                    raise typer.Abort()
            else:
                repo = cfg.get_repository(name)

            m = Repository(repo.path)

            installed_versions = len(m.versions.instances())

            parts = []
            parts.append(tr("已安装的版本数：[repr.number]{}[/]", installed_versions))

            console.print(Panel(
                Group(*parts),
                title=repo.name, border_style='yellow', title_align='left'
            ))

        except ValueError:
            console.error(tr("未找到此名称的储存库"))

    async def remove(self, name: str, yes: bool = typer.Option(False, '-y', '--yes')):
        if not cfg.exists_repository(name):
            console.error(tr("未找到此名称的储存库"))
            raise typer.Abort()

        rec = cfg.get_repository(name)
        installed_versions = len(Repository(rec.path).versions.instances())

        console.confirm(tr(
            "此储存库安装有 {} 个版本，删除后所有版本、个人配置、存档等信息都将不可恢复，是否继续？", installed_versions
        ), abort=True, skip=yes)

        with console.no_interrupt():
            cfg.remove_repository(name)

    async def list(self):
        repos = cfg.list_repositories()

        if not repos:
            console.print(tr("无记录的存储库"))
            return

        table = Table(
            tr("储存库名"), tr("位置"),
            header_style="bold green",
            box=rich.box.ROUNDED
        )
        for rec in repos:
            table.add_row(
                f'[bold]{rec.name}[/bold]',
                f'[green]{rec.path}[/green]'
            )

        console.print(table)

        console.print(tr("[dim]当前选中的是 [bold]{}[/bold][/dim]", cfg.get_selected_repository().name))

    async def select(self, name: str):
        if not cfg.exists_repository(name):
            console.error(tr("此名称的存储库不存在"))
            raise typer.Abort()

        with console.no_interrupt():
            cfg.set_selected_repository(name)
