from typing import Literal

import typer
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel

from app.core.i18n import tr
from app.core.minecraft import VersionManifestModel
from app.core.minecraft.minecraft_version import MinecraftVersion
from app.interfaces.command.command import Command
from app.interfaces.command.common import typer_app, console
from app.interfaces.command.methods import find_repo, call_and_cache


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

    async def main(
            self,
            version=None,
            *,
            online: bool = False,
            repo: str | None = typer.Option(None, '-r', '--repo'),
            type: Literal['release', 'snapshot', 'all'] = typer.Option('release', '-t', "--type"),
            full: bool = typer.Option(False, '-f', '--full')
    ):
        minecraft = find_repo(repo, ask=False)

        online_manifest = None
        if online:
            online_manifest = await call_and_cache(
                url="https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
                type=VersionManifestModel,
                name="版本清单",
                cacher=minecraft.launcher_data.cache,
                key='versionmeta:manifest'
            )

        if version is None and online_manifest:
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
            for version in online_manifest.versions:
                mc_version = MinecraftVersion(version.id)

                if mc_version.type == 'old':  # 远古版本的版本号解析并不成熟，同时也没有计划支持远古版本，直接排除
                    continue

                if not full and online:
                    if (key := get_version_without_patch(mc_version)) in record:
                        continue
                    record.add(key)

                version_groups[mc_version.type.removesuffix('(legacy)')].append(mc_version)

        else:
            if minecraft is None:
                console.error("无法列出本地版本")
                console.tip(
                    tr("你可以通过添加 [green]--online[/green] 标志在线获取版本列表，但这样你将无法看到本地版本"))

        text_mapping = {
            'release': (tr("正式版"), 'green'),
            'april fool': (tr("愚人节版本"), 'yellow'),
            'snapshot': (tr("快照版"), 'tan'),
            'rc': (tr("预览版"), 'medium_purple1'),
            'pre': (tr("预发布版"), 'sky_blue1'),
        }
        panels = []

        for type, (text, style) in text_mapping.items():
            type = type.removesuffix("(legacy)")
            group = version_groups[type]
            if not group:
                continue

            panels.append(Panel(
                Group(
                    *[
                        f" [green]*[/green] [bold]{v.version}[/bold]"
                        for v in group
                    ]
                ),
                title=text, title_align='left', border_style=style
            ))

        if broken_versions := version_groups['broken']:
            panels.append(Panel(
                Group(
                    *[
                        f" [red]*[/red] [bold]{v.name}[/bold]"
                        for v in broken_versions
                    ]
                ),
                title=tr("损坏的版本"), title_align='left', border_style='red'
            ))

        panels.sort(key=lambda x: len(x.renderable.renderables), reverse=True)

        console.print(Columns(panels, align='center', expand=True))

        if not full:
            console.print(f"\n\n[dim]{tr('仅显示每个主版本的最新子版本，如果想要完整的版本号列表，请使用 --full')}[/dim]")
