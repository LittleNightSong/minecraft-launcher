from typing import Literal

import typer
from rich.panel import Panel

from app.common.concurrent_ import as_sync
from app.i18n.translator import tr
from app.interfaces.command.ac_install import find_repo
from app.interfaces.command.common import typer_app, console
from app.interfaces.command.methods import get_version_manifest
from app.minecraft.version_parser import MinecraftVersion
from app.resources.instance import InstanceDirectory
from app.resources.repository import Repository


# @trace
def get_version_without_patch(version: MinecraftVersion):
    match version.type:
        case x if x in {'release', 'pre', 'snapshot', 'rc'}:
            return x, version.major, version.minor
        case 'snapshot(legacy)':
            return version.year
        case _:
            return version.version


@typer_app.command()
@as_sync
async def list(
        version=None,
        *,
        online: bool = False,
        repo: str | None = typer.Option(None, '-r', '--repo'),
        type: Literal['release', 'snapshot', 'all'] = typer.Option('release', '-t', "--type"),
        full: bool = typer.Option(False, '-f', '--full')
):
    repo = find_repo(repo, ask=False)
    if repo is None:
        console.print(f'[red]{tr("错误：无法找到且没有指定储存库")}[/red]')

    minecraft = Repository(repo)

    if online:
        manifest = await get_version_manifest()
    else:
        manifest = {'versions': minecraft.versions.instances(skip_broken=False)}

    if version is None and online:
        latest = manifest['latest']
        console.print(Panel(
            f" [green]*[/green] Release  [bold]{latest['release']}[/bold]\n"
            f" [green]*[/green] Snapshot [bold]{latest['snapshot']}[/bold]",
            title=tr("最新版"), title_align='left'
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

    for version in manifest['versions']:
        if online:
            if type != 'all' and version['type'] != type:
                continue

            if version['id'].startswith('b'):
                continue

        elif isinstance(version, InstanceDirectory) and not version.check():
            version_groups['broken'].append(version)
            continue

        mc_version = MinecraftVersion(version['id'])
        if not full and online:
            if (key := get_version_without_patch(mc_version)) in record:
                continue
            record.add(key)

        version_groups[mc_version.type.removesuffix('(legacy)')].append(mc_version)

    text_mapping = {
        'release': tr("正式版"),
        'april fool': tr("愚人节版本"),
        'snapshot': tr("快照版"),
        'rc': tr("预览版"),
        'pre': tr("预发布版"),
    }

    for type, text in text_mapping.items():
        type = type.removesuffix("(legacy)")
        group = version_groups[type]
        if not group:
            continue

        console.print(Panel(
            '\n'.join([
                f" [green]*[/green] [bold]{v.version}[/bold]"
                for v in group]),
            title=text, title_align='left'
        ))

    if broken_versions := version_groups['broken']:
        console.print(Panel(
            '\n'.join([
                f" [red]*[/red] [bold]{v.name}[/bold]"
                for v in broken_versions
            ]), title=tr("损坏的版本"), title_align='left'
        ))

    if not full:
        console.print(f"\n\n[dim]{tr('仅显示每个主版本的最新子版本，如果想要完整的版本号列表，请使用 --full')}[/dim]")
