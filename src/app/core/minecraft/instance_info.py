"""
实例信息统计模块。

为 ``show`` 命令收集单个实例的概况: 类型、版本号、占用空间、各类内容数量,
以及从客户端 jar 中读取的资源包 / 数据包格式版本。

这里的函数只做"读取与统计", 不涉及任何输出或样式, 方便在其它界面中复用。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import msgspec
from loguru import logger

from app.core.files.client_version import ClientVersionJson, read_client_version_jar
from app.core.minecraft.instance_metadata import detect_loader, version_candidate
from app.core.minecraft.version import MinecraftVersion

# 资源包 / 光影包常见的文件后缀
_ARCHIVE_SUFFIXES = ('.zip', '.jar')

# 目录中的忽略项 (例如光影包旁的说明文件)
_IGNORED_NAMES = {'desktop.ini', 'thumbs.db'}

# 缓存目录, 统计占用空间时跳过
_CACHE_DIR_NAMES = {'.cache', '.qmenu_opened.marker'}


@dataclass
class InstanceContentCount:
    """实例内各类内容的数量"""
    saves: int = 0
    resourcepacks: int = 0
    shaderpacks: int = 0
    mods: int = 0
    datapacks: int = 0


@dataclass
class InstanceInfo:
    """
    实例概况

    :ivar name: 实例名称
    :ivar kind: 实例类型, 例如 ``原版`` / ``fabric``
    :ivar version: 原版版本号
    :ivar loader: 加载器类型
    :ivar loader_version: 加载器版本号
    :ivar path: 实例目录
    :ivar size: 占用空间 (字节)
    :ivar content: 各类内容数量
    :ivar client_version: 从客户端 jar 中读到的 version.json
    :ivar notes: 读取过程中的说明
    """
    name: str
    kind: str
    version: str | None = None
    loader: str | None = None
    loader_version: str | None = None
    path: Path | None = None
    size: int = 0
    content: InstanceContentCount = field(default_factory=InstanceContentCount)
    client_version: ClientVersionJson | None = None
    notes: list[str] = field(default_factory=list)


def _count_dir(directory: Path, *, suffixes: tuple[str, ...] | None = None) -> int:
    """
    统计目录中的条目数量

    :param directory: 目标目录
    :param suffixes: 只统计这些后缀的文件; 为 None 时统计所有子目录与文件
    """
    try:
        entries = list(directory.iterdir())
    except OSError:
        return 0

    count = 0

    for entry in entries:
        if entry.name.lower() in _IGNORED_NAMES:
            continue

        try:
            if suffixes is None:
                if entry.is_dir() or entry.is_file():
                    count += 1
            elif entry.is_file() and entry.suffix.lower() in suffixes:
                count += 1
        except OSError:
            continue

    return count


def _dir_size(directory: Path, *, _depth: int = 0) -> int:
    """
    递归统计目录占用的空间

    符号链接 / 目录联接本身只有很小的开销, 统计它们的目标会导致把整个缓存算进来,
    因此这里跳过链接, 只累加真实文件。

    :param directory: 目标目录
    :param _depth: 当前递归深度 (内部使用)
    """
    total = 0

    try:
        entries = os.scandir(directory)
    except OSError:
        return 0

    with entries:
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue

                if entry.is_dir(follow_symlinks=False):
                    total += _dir_size(Path(entry.path), _depth=_depth + 1)
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue

    return total


def _classify(version: str | None, loader: str | None, loader_version: str | None) -> str:
    """把实例归类为便于展示的类型"""
    if not loader:
        return '原版'

    if loader_version:
        return f'{loader} {loader_version}'

    return loader


def _read_client_version(instance) -> tuple[ClientVersionJson | None, list[str]]:
    """从客户端 jar 中读取 version.json, 读取不到时返回 None 与原因"""
    main_file = instance.main_file

    if main_file.is_symlink() and not main_file.exists():
        # PCL 之类的启动器会把主文件链接到自己的缓存, 缓存被清理后就成了失效链接
        return None, [f'客户端主文件是失效的链接（{_read_link(main_file)}），重新安装或补回该文件后可读取']

    if not main_file.is_file():
        return None, ['找不到客户端主文件']

    data = read_client_version_jar(main_file)

    if data is None:
        # 1.14 之前的客户端 jar 中没有 version.json
        return None, ['客户端主文件中没有 version.json']

    return data, []


def _read_link(path: Path) -> str:
    """读取符号链接的目标, 失败时返回原路径"""
    try:
        target = str(path.readlink())
    except OSError:
        return str(path)

    # Windows 上 readlink 可能带 \\?\ 前缀, 展示时去掉
    return target.removeprefix('\\\\?\\')


def collect_instance_info(instance, *, compute_size: bool = True) -> InstanceInfo:
    """
    收集实例的概况信息

    :param instance: ``InstanceDirectory`` 对象
    :param compute_size: 是否统计占用空间 (大目录可能较慢)
    :return: 实例概况
    """
    notes: list[str] = []

    meta = None
    try:
        meta = instance.version_meta
    except FileNotFoundError:
        notes.append('没有 .mpk 描述文件')
    except Exception as exc:
        # 文件存在但无法解析: 多半是由更早的版本写出、缺少新字段的旧格式
        logger.debug("解析实例 {!r} 的 .mpk 失败: {}", instance.name, exc)
        notes.append(f'.mpk 描述文件无法解析（{exc}），可运行 fix-instance-metadata --force 重建')

    version = getattr(meta, 'version', None)
    loader = getattr(meta, 'loader', None)
    loader_version = getattr(meta, 'loader_version', None)

    if version is None or loader is None:
        # .mpk 不可用时退回版本 JSON 推断版本号与加载器
        try:
            raw = msgspec.json.decode(instance.mojang_meta_file.read_bytes())
        except (OSError, ValueError):
            raw = None

        if isinstance(raw, dict):
            if version is None:
                version = version_candidate(raw.get('clientVersion')) or version_candidate(raw.get('id'))

            if loader is None:
                loader = detect_loader(raw)

    info = InstanceInfo(
        name=instance.name,
        kind=_classify(version, loader, loader_version),
        version=version,
        loader=loader,
        loader_version=loader_version,
        path=Path(instance.path),
    )

    # ---------------------------------------------------------------- 内容数量
    info.content = InstanceContentCount(
        saves=_count_dir(instance.saves_dir),
        # 资源包 / 光影包目录中可能混有说明文件, 只统计压缩包
        resourcepacks=_count_dir(instance.resourcepacks_dir, suffixes=_ARCHIVE_SUFFIXES),
        shaderpacks=_count_dir(instance.shaderpacks_dir, suffixes=_ARCHIVE_SUFFIXES),
        mods=len(instance.all_mod_files),
        datapacks=_count_dir(instance.datapacks_dir, suffixes=_ARCHIVE_SUFFIXES),
    )

    # ---------------------------------------------------------------- 空间占用
    if compute_size:
        info.size = _dir_size(Path(instance.path))

    # ---------------------------------------------------------------- 版本信息
    client_version, client_notes = _read_client_version(instance)
    info.client_version = client_version
    notes.extend(client_notes)

    if version is not None:
        try:
            MinecraftVersion.from_string(version)
        except Exception:
            notes.append('版本号无法解析')

    info.notes = notes
    return info
