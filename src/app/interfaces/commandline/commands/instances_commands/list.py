from typing import Iterable, Literal

import re

import msgspec
import typer
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from app.core.i18n import tr
from app.core.minecraft import MinecraftVersion
from app.core.network import Session
from app.interfaces.commandline import typer_app
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.methods import find_repository

# 展示顺序, 同时决定了面板的顺序来源
_VERSION_TYPES = ('release', 'snapshot', 'pre', 'rc', 'april fool')

# 看起来像版本号的字符串, 用来排除"整合包名"这类被解析器误判为愚人节版本的值
# 例如 1.20.4 / 26w14a / 22w13oneblockatatime / 1.RV-Pre1
_LOOKS_LIKE_VERSION = re.compile(r'(?:^\d+\.\d+|\d{2}w\d{2}|\d+\.RV)')


def get_version_without_patch(version: MinecraftVersion):
    """
    获取用于"合并子版本"的分组键, 同键的版本在非 --full 模式下只保留最新的一个

    正式版按 主版本.次版本 合并 (1.20.2 / 1.20.4 视为同一组),
    其余可解析的版本则使用自身的版本号, 也就是只做去重
    """
    match version.type:
        case x if x in {'release', 'pre', 'rc'}:
            return f'common.{version.major}.{version.minor}'
        case x if x in {'snapshot', 'snapshot(legacy)'}:
            return f'snapshot.{version.version}'
        case _:
            return f'{version.type}.{version.version}'


def _version_key(version: MinecraftVersion):
    """为版本提供一个稳定的排序键, 避免旧版本的比较函数在混合类型时返回 None"""

    def snap_order(snap):
        # 没有编号的版本 (也就是正式版) 视为比它的预发布版更新
        return float('inf') if not snap else snap

    if (major := getattr(version, 'major', None)) is not None:
        return (0, major, version.minor or 0, version.patch or 0, snap_order(version.snap), version.version)

    if (year := getattr(version, 'year', None)) is not None:
        return (1, year, version.week or 0, version.suffix or '', version.version)

    return (2, version.version)


def _resolve_mojang_version(instance) -> MinecraftVersion | None:
    """
    解析实例对应的 Minecraft 版本

    优先级从高到低:

    1. 实例自己的 ``.mpk`` 元数据 (本启动器安装或修复过的实例都以它为准);
    2. 实例目录中的版本 JSON;
    3. 实例名称。

    第三方启动器写出的 JSON 里, ``id`` 往往是整合包自身的名字 (例如 ``Radiance``),
    直接拿去解析会被当成无法识别的愚人节版本, 因此不能作为首选。
    """
    # ---------------------------------------------------------------- 1. 优先使用 .mpk
    try:
        meta = instance.version_meta
    except Exception:
        meta = None

    if meta is not None:
        for value in (getattr(meta, 'version', None),):
            if (version := _version_or_none(value)) is not None:
                return version

    # ---------------------------------------------------------------- 2. 版本 JSON
    try:
        raw = msgspec.json.decode(instance.mojang_meta_file.read_bytes())
    except (OSError, ValueError):
        raw = None

    if isinstance(raw, dict):
        for key in ('id', 'clientVersion'):
            if (version := _version_or_none(raw.get(key))) is not None:
                return version

    # ---------------------------------------------------------------- 3. 实例名称
    return _version_or_none(instance.name)


def _version_or_none(value) -> MinecraftVersion | None:
    """把字符串转换成版本对象, 无法可靠识别时返回 None"""
    if not isinstance(value, str) or not value.strip():
        return None

    version = MinecraftVersion.from_string(value)

    # 解析器会把一切无法识别的字符串都归为愚人节版本, 单纯的名字不应算作版本号
    if version.type == 'april fool' and not _LOOKS_LIKE_VERSION.search(value):
        return None

    return version


def _local_label(instance, mc_version: MinecraftVersion) -> str:
    """本地实例的展示文本, 与原版版本号不同的实例额外标注其对应的版本"""
    if instance.name == mc_version.version:
        return f'{instance.name}'

    return f'{instance.name} ({mc_version.version})'


def _collect(
        entries: Iterable[tuple[str, MinecraftVersion]],
        *,
        version: str | None,
        type: str | None,
        full: bool,
) -> dict[str, list[tuple[str, MinecraftVersion]]]:
    groups: dict[str, list[tuple[str, MinecraftVersion]]] = {t: [] for t in _VERSION_TYPES}

    for label, mc_version in entries:
        if mc_version.type == 'old':  # 远古版本的版本号解析并不成熟，同时也没有计划支持远古版本，直接排除
            continue

        if type is not None and mc_version.main_type != type:
            continue

        if version:
            # 本地实例的名称可能与 Minecraft 版本号无关, 因此名称和版本号任一匹配即可
            if not (mc_version.version.startswith(version) or label.startswith(version)):
                continue

        groups.setdefault(mc_version.main_type, []).append((label, mc_version))

    if not full:
        # 输入本身是按时间倒序的, 因此同一分组内最先遇到的即为最新的版本
        seen = set()
        for group in groups.values():
            unique = []
            for label, mc_version in group:
                key = get_version_without_patch(mc_version)
                if key in seen:
                    continue

                seen.add(key)
                unique.append((label, mc_version))

            group[:] = unique

    for group in groups.values():
        group.sort(key=lambda item: _version_key(item[1]), reverse=True)

    return groups


def _render(groups: dict[str, list[tuple[str, MinecraftVersion]]]):
    text_mapping = {
        'release': tr("正式版"),
        'april fool': tr("愚人节版本"),
        'snapshot': tr("快照版"),
        'rc': tr("预览版"),
        'pre': tr("预发布版"),
    }
    panels = []

    for type, text in text_mapping.items():
        if not (group := groups.get(type)):
            continue

        panels.append(Panel(
            Group(*[
                # 实例名来自用户, 不能当作标记解析
                Text("* ") + Text(label, style='bold')
                for label, _ in group
            ]),
            title=text, title_align='left', border_style=f"vtype.{type.replace(' ', '-')}"
        ))

    return panels


def _render_broken(names: list[str]):
    return Panel(
        Group(*[
            Text("* ", style='red') + Text(name, style='bold red')
            for name in names
        ]),
        title=tr("损坏的版本"), title_align='left', border_style='red'
    )


class ListCommand(Command, app=typer_app):
    name = 'list'

    async def init(self): ...

    async def main(
            self,
            version: str | None = typer.Argument(None),
            *,
            online: bool = typer.Option(False, '--online'),
            repo: str | None = typer.Option(None, '-r', '--repo'),
            type: Literal['release', 'snapshot', 'all'] | None = typer.Option(None, '-t', "--type"),
            full: bool = typer.Option(False, '-f', '--full'),
    ):
        """
        列出可用的 Minecraft 版本

        :param version: 只列出以此开头的版本或实例, 例如 1.21
        :param online: 从 Mojang 在线获取版本列表, 而不是读取本地实例
        :param repo: 储存库名称或路径, 默认为当前选中的储存库
        :param type: 只列出指定类型的版本
        :param full: 显示全部子版本, 否则只显示每个主版本的最新子版本
        """
        from app.third_party.mojang import MinecraftAPI

        filter_type = None if type == 'all' else type

        entries: list[tuple[str, MinecraftVersion]] = []
        broken_versions: list[str] = []
        latest_panel = None

        if online:
            api = MinecraftAPI(Session())
            online_manifest = await api.fetch_version_manifest()

            if filter_type is None and version is None:
                latest = online_manifest.latest
                latest_panel = Panel(
                    f" [green]*[/green] Release  [bold]{latest.release}[/bold]\n"
                    f" [green]*[/green] Snapshot [bold]{latest.snapshot}[/bold]",
                    title=tr("最新版"), title_align='left', border_style='bright_cyan',
                )

            entries = [
                (v.id, MinecraftVersion.from_string(v.id))
                for v in online_manifest.versions
            ]

        else:
            minecraft = find_repository(repo)

            if minecraft is None:
                console.error(tr("未指定本地储存库或指定的存储库无效"))
                console.error(tr("无法列出本地版本"))
                console.tip(
                    tr("你可以通过添加 [tty.option]--online[/] 标志在线获取版本列表，但这样你将无法看到本地版本"))
                raise typer.Abort()

            for instance in minecraft.versions.instances(skip_broken=False):
                if not instance.is_valid():
                    broken_versions.append(instance.name)
                    continue

                if (mc_version := _resolve_mojang_version(instance)) is None:
                    broken_versions.append(instance.name)
                    continue

                if version and not (instance.name.startswith(version) or mc_version.version.startswith(version)):
                    continue

                entries.append((_local_label(instance, mc_version), mc_version))

        groups = _collect(entries, version=version, type=filter_type, full=full)

        panels = _render(groups)

        if broken_versions:
            broken_panel = _render_broken(broken_versions)

            if panels:
                panels.append(broken_panel)
            else:
                panels = [broken_panel]

        if not panels and not any(groups.values()):
            if entries or broken_versions:
                console.print(tr("没有符合条件的版本"))
            else:
                console.print(tr("没有可列出的版本"))

        if panels:
            panels.sort(key=lambda x: len(x.renderable.renderables), reverse=True)

            if latest_panel is not None:
                # 让"最新版"面板和列表共用同一套列布局, 否则它会被独占一行并贴在最左边
                panels.insert(0, latest_panel)

            console.print(Columns(panels, align='center', expand=True))

        if not full:
            console.print(
                f"\n\n[dim]{tr('仅显示每个主版本的最新子版本，如果想要完整的版本号列表，请使用 [tty.option]--full[/]')}[/dim]")
