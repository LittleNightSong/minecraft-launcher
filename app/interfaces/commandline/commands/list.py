from typing import Literal

import msgspec
import typer
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel

from app.core.i18n import tr
from app.core.minecraft import MinecraftVersion, MinecraftAPI
from app.core.network import Session
from app.interfaces.commandline import typer_app
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.methods import find_repository


# @trace
def get_version_without_patch(version: MinecraftVersion):
    match version.type:
        case x if x in {'release', 'pre', 'snapshot', 'rc'}:
            return x, version.major, version.minor
        case 'snapshot(legacy)':
            return version.year
        case _:
            return version.version


class ListCommand(Command, app=typer_app):
    name = 'list'

    async def init(self): ...

    async def main(
            self,
            version=None,
            *,
            online: bool = False,
            repo: str | None = typer.Option(None, '-r', '--repo'),
            type: Literal['release', 'snapshot', 'all'] | None = typer.Option(None, '-t', "--type"),
            full: bool = typer.Option(False, '-f', '--full')
    ):
        minecraft = find_repository(repo, ask=False)

        online_manifest = None
        if online:
            api = MinecraftAPI(Session(), cacher=minecraft.launcher_data.cacher)
            online_manifest = await api.get_version_manifest()

        if type is None and version is None and online_manifest is not None:
            latest = online_manifest.latest
            console.print(Panel(
                f" [green]*[/green] Release  [bold]{latest.release}[/bold]\n"
                f" [green]*[/green] Snapshot [bold]{latest.snapshot}[/bold]",
                title=tr("最新版"), title_align='left', border_style='bright_cyan',
            ))

        record = set()
        version_groups = {
            'rc': [],
            'pre': [],
            'snapshot': [],
            'release': [],
            'april fool': [],
            'broken': [],
        }
        if online:
            for v in online_manifest.versions:
                mc_version = MinecraftVersion(v.id)

                if mc_version.type == 'old':  # 远古版本的版本号解析并不成熟，同时也没有计划支持远古版本，直接排除
                    continue

                if type is None and not full and online:
                    if (key := get_version_without_patch(mc_version)) in record:
                        continue
                    record.add(key)

                if type and mc_version.simple_type != type:
                    continue

                if version and not v.id.startswith(version):
                    continue

                version_groups[mc_version.simple_type].append(mc_version.version)

        else:
            if minecraft is None:
                console.error(tr("未指定本地储存库或指定的存储库无效"))
                console.error(tr("无法列出本地版本"))
                console.tip(
                    tr("你可以通过添加 [tty.option]--online[/] 标志在线获取版本列表，但这样你将无法看到本地版本"))
                raise typer.Abort()

            for instance in minecraft.versions:
                try:
                    mc_version = MinecraftVersion(instance.version_meta.id)
                except msgspec.ValidationError:
                    version_groups['broken'].append(instance.name)
                    continue

                if type is None and not full:
                    if mc_version.type == 'old': continue
                    if (key := get_version_without_patch(mc_version)) in record:
                        continue

                    record.add(key)

                if type and mc_version.simple_type != type:
                    continue

                if version and not mc_version.version.startswith(version):
                    continue

                version_groups[mc_version.simple_type].append(
                    f'{instance.name} ({instance.version_meta.id})')

        text_mapping = {
            'release': tr("正式版"),
            'april fool': tr("愚人节版本"),
            'snapshot': tr("快照版"),
            'rc': tr("预览版"),
            'pre': tr("预发布版"),
        }
        panels = []

        for type, text in text_mapping.items():
            group = version_groups[type]
            if not group:
                continue

            panels.append(Panel(
                Group(
                    *[
                        f" [green]*[/green] [bold]{v}[/bold]"
                        for v in group
                    ]
                ),
                title=text, title_align='left', border_style=f"vtype.{type.replace(' ', '-')}"
            ))

        if broken_versions := version_groups['broken']:
            panels.append(Panel(
                Group(
                    *[
                        f" [red]*[/red] [bold]{v}[/bold]"
                        for v in broken_versions
                    ]
                ),
                title=tr("损坏的版本"), title_align='left', border_style='red'
            ))

        panels.sort(key=lambda x: len(x.renderable.renderables), reverse=True)

        console.print(Columns(panels, align='center', expand=True))

        if not full:
            console.print(
                f"\n\n[dim]{tr('仅显示每个主版本的最新子版本，如果想要完整的版本号列表，请使用 [tty.option]--full[/]')}[/dim]")
