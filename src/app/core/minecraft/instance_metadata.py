"""
实例元数据修复模块。

启动器使用自己的数据结构 (``VersionMeta``) 和文件格式 (``.mpk``) 存放实例元数据,
而其它启动器 (例如 PCL) 只会写出 Mojang 格式的 ``.json`` 版本描述文件。
本模块负责把这些 ``.json`` 转换为启动器自己的 ``.mpk``, 并在字段缺失时自动推断。

转换过程分为三步:

1. 规范化 (normalize): 补齐第三方启动器省略的字段, 并把 ``_libraries``、
   ``clientVersion`` 之类的私有扩展映射到标准字段上;
2. 统一 (unify): 复用 ``VersionMetaModel.unify`` 把 Mojang 模型转换为 ``VersionMeta``;
3. 推断 (infer): 推断加载器类型与加载器版本、原版版本号, 以及客户端主文件。

推断是尽力而为的: 网络操作可以整体关闭, 关闭后仅使用本地信息, 完全不访问网络。
"""

from __future__ import annotations

import asyncio
import copy
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import msgspec
from loguru import logger

from app.core.i18n import tr
from app.core.models import Library
from app.core.minecraft.version import MinecraftVersion
from app.core.models.version_meta import VersionMeta

LoaderType = Literal['forge', 'fabric', 'neoforge']
"""启动器支持的加载器类型"""

# 加载器的识别特征: (主类名前缀, 依赖库坐标前缀)
# 注意: cpw.mods.bootstraplauncher 是 1.17 之后 Forge 与 NeoForge 共用的启动器, 不能作为识别依据;
#      NeoForge 从 1.20.5 开始使用 net.neoforged.fml, 而 Forge 始终是 net.minecraftforge.fml。
_LOADER_SIGNATURES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    'fabric': (
        (
            'net.fabricmc.loader.impl.launch',
            'net.fabricmc.loader.launch',
        ),
        (
            'net.fabricmc:fabric-loader:',
            'net.fabricmc:fabric:',
        ),
    ),
    'neoforge': (
        (
            'net.neoforged',
        ),
        (
            'net.neoforged:neoforge:',
            'net.neoforged:forge:',
            'net.neoforged.fml:',
            'net.neoforged.fancymodloader:',
        ),
    ),
    'forge': (
        (
            'net.minecraftforge.fml',
        ),
        (
            'net.minecraftforge:forge:',
            'net.minecraftforge:fmlloader:',
            'net.minecraftforge:server:',
        ),
    ),
}

# 识别顺序: 先认领区分度最高的特征
_LOADER_ORDER: tuple[str, ...] = ('fabric', 'neoforge', 'forge')

# 加载器在实例目录或仓库的 libraries 目录中可能出现的位置
_LOADER_DIR_PATTERNS = {
    'fabric': ('net/fabricmc/fabric-loader',),
    'neoforge': ('net/neoforged/neoforge', 'net/neoforged/forge'),
    'forge': ('net/minecraftforge/forge',),
}

# 加载器依赖库坐标的前缀, 用于提取加载器版本号
_LOADER_LIBRARY_PREFIXES = {
    'fabric': ('net.fabricmc:fabric-loader:', 'net.fabricmc:fabric:'),
    'neoforge': ('net.neoforged:neoforge:', 'net.neoforged:forge:'),
    'forge': ('net.minecraftforge:forge:', 'net.minecraftforge:fmlloader:'),
}

# 形如 1.20.4 / 1.21 / 26.1.2 的正式版版本号
_RELEASE_VERSION = re.compile(r'\d+\.\d+(?:\.\d+)?')

# 形如 23w13a / 26w14a 的快照版本号, 允许 20w14infinite 这类后缀
_SNAPSHOT_VERSION = re.compile(r'\d{2}w\d{2}[a-z](?:[a-z_]\w*)?')

# 愚人节版本号的常见形态, 例如 22w13oneblockatatime / 1.RV-Pre1 / 20w14infinite
_APRIL_FOOL_VERSION = re.compile(r'(?:\d{2}w\d{2}\w+|1\.(?:RV|9|\d{1,2}\.(?:1|2|22)))')

# 客户端主文件在实例目录中的候选位置
_CLIENT_JAR_CANDIDATES = (
    '{name}.jar',
    '{id}.jar',
    '{mc}.jar',
    'bin/{name}.jar',
    'bin/{mc}.jar',
    'bin/minecraft.jar',
)


class FixStatus:
    """修复状态常量"""
    FIXED = 'fixed'
    SKIPPED = 'skipped'
    FAILED = 'failed'


@dataclass
class FixResult:
    """
    单个实例的修复结果。

    :ivar name: 实例名称
    :ivar status: ``fixed`` / ``skipped`` / ``failed``
    :ivar version: 推断出的原版版本号
    :ivar loader: 推断出的加载器类型
    :ivar loader_version: 推断出的加载器版本号
    :ivar client_jar: 客户端主文件使用的本地路径或下载地址
    :ivar notes: 推断过程中的补充说明
    :ivar error: 失败原因
    """
    name: str
    status: str
    version: str | None = None
    loader: str | None = None
    loader_version: str | None = None
    client_jar: str | None = None
    notes: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status != FixStatus.FAILED


class ClientJarNotResolved(Exception):
    """客户端主文件既没有下载地址, 本地也找不到"""


# ---------------------------------------------------------------------------------------------------------------------
# 规范化: 把第三方启动器写出的 json 变成 VersionMetaModel 可以接受的样子
# ---------------------------------------------------------------------------------------------------------------------

def _first_string(raw: dict, *keys) -> str | None:
    """返回第一个存在且为非空字符串的字段"""
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return None


def _parse_time(value) -> datetime:
    """把 json 中的时间字段解析成 datetime, 无法解析时返回当前时间"""
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return msgspec.convert(value, datetime)
        except msgspec.ValidationError:
            pass

    return datetime.now(timezone.utc).replace(tzinfo=None)


def library_path(name: str) -> str | None:
    """由 Maven 坐标得到依赖库的相对路径, 坐标不完整时返回 None"""
    try:
        return str(Library(name).path)
    except ValueError:
        return None


def _normalize_download(raw: dict | None, path: str | None = None, *, fill_missing: bool = True) -> dict:
    """规整一个下载条目, 字段缺失时补上空值"""
    raw = dict(raw or {})

    if path and not raw.get('path'):
        raw['path'] = path

    if fill_missing:
        raw.setdefault('sha1', None)
        raw.setdefault('size', None)
        raw.setdefault('url', None)

    return raw


def normalize_libraries(raw: dict) -> list[dict]:
    """
    规整依赖库列表

    - 部分启动器 (例如 PCL) 会把依赖库放在 ``_libraries`` 中;
    - 缺少 ``downloads`` 的依赖库 (例如手动安装的 OptiFine) 会补上一个只有坐标与
      路径的空壳, 从而保留该依赖而不是直接丢弃;
    - 缺少部分字段的下载条目补上空值。
    """
    libraries = raw.get('libraries')
    if not isinstance(libraries, list):
        libraries = raw.get('_libraries')

    if not isinstance(libraries, list):
        return []

    normalized = []

    for lib in libraries:
        if not isinstance(lib, dict) or not isinstance(lib.get('name'), str):
            continue

        lib = dict(lib)
        downloads = lib.get('downloads')
        downloads = dict(downloads) if isinstance(downloads, dict) else {}

        synthesized = False

        if downloads.get('artifact') is None and not lib.get('natives'):
            path = library_path(lib['name'])

            if path is None:
                logger.warning("依赖库 {!r} 的坐标不完整，已跳过", lib['name'])
                continue

            # 已有的下载信息里可能只有 classifiers, 此时保留它们。
            # 这类依赖没有校验值, 用空值占位: 下游模型要求非空的字符串与整数,
            # 而校验流程会把空字符串与 0 当作"无需校验", 因此不会误判为文件损坏
            downloads['artifact'] = {
                'path': path,
                'sha1': '',
                'size': 0,
                'url': '',
            }
            synthesized = True

        if isinstance(downloads.get('artifact'), dict) and not synthesized:
            downloads['artifact'] = _normalize_download(downloads['artifact'], library_path(lib['name']))

        if isinstance(downloads.get('classifiers'), dict):
            downloads['classifiers'] = {
                name: _normalize_download(value)
                for name, value in downloads['classifiers'].items()
            }

        lib['downloads'] = downloads
        normalized.append(lib)

    return normalized


def _guess_java_major(version: str) -> int:
    """根据 Minecraft 版本号粗略推断所需的 Java 主版本"""
    if _SNAPSHOT_VERSION.fullmatch(version):
        # 快照版本跟随当时的正式版, 统一给一个足够新的版本
        return 21

    if not _RELEASE_VERSION.fullmatch(version):
        return 8

    major, minor = (int(x) for x in version.split('.')[:2])

    if major >= 26 or (major, minor) >= (1, 20):
        return 21
    if (major, minor) >= (1, 18):
        return 17
    if (major, minor) >= (1, 17):
        return 16
    return 8


def normalize_version_json(raw: dict) -> dict:
    """
    把第三方启动器的版本 JSON 规范化成 Mojang 格式

    只做"补齐与映射", 不修改任何已经有效的字段。

    :param raw: 原始 JSON
    :return: 规范化后的 JSON (新字典, 不会修改入参)
    """
    raw = copy.deepcopy(raw)

    raw['libraries'] = normalize_libraries(raw)
    raw.pop('_libraries', None)

    # 版本号: PCL 用 clientVersion 记录对应的原版版本
    version = _first_string(raw, 'id', 'clientVersion')
    if version is None:
        version = _first_string(raw, 'inheritsFrom') or 'unknown'
    raw['id'] = version

    if not _first_string(raw, 'type'):
        raw['type'] = 'snapshot' if _SNAPSHOT_VERSION.fullmatch(version) else 'release'

    if not isinstance(raw.get('assetIndex'), dict):
        assets = raw.get('assets')
        raw['assetIndex'] = {'id': assets} if isinstance(assets, str) else {}

    if not isinstance(raw.get('assets'), str):
        raw['assets'] = raw['assetIndex'].get('id') or 'legacy'

    if not isinstance(raw.get('javaVersion'), dict):
        raw['javaVersion'] = {'component': 'jre-legacy', 'majorVersion': _guess_java_major(version)}

    if not isinstance(raw.get('downloads'), dict):
        raw['downloads'] = {}
    if not isinstance(raw['downloads'].get('client'), dict):
        raw['downloads']['client'] = {}
    if not isinstance(raw['downloads'].get('server'), dict):
        raw['downloads']['server'] = None

    if not _first_string(raw, 'mainClass'):
        raw['mainClass'] = 'net.minecraft.client.main.Main'

    if not isinstance(raw.get('logging'), dict):
        raw['logging'] = {}

    for key in ('releaseTime', 'time'):
        raw[key] = _parse_time(raw.get(key))

    if not isinstance(raw.get('complianceLevel'), int):
        raw['complianceLevel'] = 1

    if not isinstance(raw.get('minimumLauncherVersion'), int):
        raw['minimumLauncherVersion'] = 21

    return raw


def rebuild_minimal_json(name: str, notes: list[str]) -> dict:
    """
    为严重损坏的描述文件构造一份最小可用的 JSON

    只有在规范化之后仍然无法解析时才会使用, 此时需要人工检查生成的元数据。
    """
    notes.append(tr("版本描述文件缺少关键字段，已用占位数据重建，请人工确认"))

    return normalize_version_json({
        'id': name,
        'type': 'release',
        'assetIndex': {'id': 'legacy'},
        'assets': 'legacy',
        'downloads': {},
        'javaVersion': {'component': 'jre-legacy', 'majorVersion': 8},
        'libraries': [],
        'mainClass': 'net.minecraft.client.main.Main',
        'releaseTime': None,
        'time': None,
    })


# ---------------------------------------------------------------------------------------------------------------------
# 推断
# ---------------------------------------------------------------------------------------------------------------------

def _library_names(raw: dict) -> list[str]:
    return [
        lib['name']
        for lib in raw.get('libraries', [])
        if isinstance(lib, dict) and isinstance(lib.get('name'), str)
    ]


def detect_loader(raw: dict) -> LoaderType | None:
    """
    根据主类名与依赖库判断实例使用的加载器

    判断依据按可靠性排序: 主类名优先, 其次是加载器自身的依赖库坐标。
    """
    main_class = (_first_string(raw, 'mainClass') or '').lower()
    names = [name.lower() for name in _library_names(raw)]

    # 先把所有证据收集起来, 避免"先匹配到谁就是谁"
    hits = {}

    for loader in _LOADER_ORDER:
        main_prefixes, library_prefixes = _LOADER_SIGNATURES[loader]

        hits[loader] = (
            any(main_class.startswith(prefix) for prefix in main_prefixes),
            any(name.startswith(prefix) for name in names for prefix in library_prefixes),
        )

    for loader in _LOADER_ORDER:
        if hits[loader][0]:
            return loader  # type: ignore[return-value]

    for loader in _LOADER_ORDER:
        if hits[loader][1]:
            return loader  # type: ignore[return-value]

    return None


def version_from_name(name: str) -> str | None:
    """从实例名称中找出最可能代表原版版本号的片段"""
    if match := _RELEASE_VERSION.search(name):
        return match.group(0)

    if match := _SNAPSHOT_VERSION.search(name):
        return match.group(0)

    return None


def _loader_version_from_name(name: str, loader: LoaderType) -> str | None:
    """从 ``1.21.1-Fabric 0.19.3``、``1.20.4-fabric-0.19.3`` 这类名称中取出加载器版本"""
    pattern = rf'[-\s]{loader}[-\s]+v?(\d[\w.+]*)'
    if match := re.search(pattern, name, re.IGNORECASE | re.ASCII):
        return match.group(1)

    return None


def _version_from_name_for_loader(name: str, loader: LoaderType) -> str | None:
    """取出名称中位于加载器之前的原版版本号"""
    pattern = rf'[-\s]{loader}[-\s]+v?\d'
    if match := re.search(pattern, name, re.IGNORECASE | re.ASCII):
        return version_from_name(name[:match.start()])

    return version_from_name(name)


def loader_version_from_libraries(raw: dict, loader: LoaderType) -> str | None:
    """从依赖库坐标中提取加载器版本"""
    prefixes = _LOADER_LIBRARY_PREFIXES[loader]

    for name in _library_names(raw):
        lowered = name.lower()

        for prefix in prefixes:
            if not lowered.startswith(prefix):
                continue

            version = name[len(prefix):].split(':')[0]

            if loader == 'forge' and '-' in version:
                # Forge 的坐标形如 1.20.1-47.2.0, 这里只取加载器自身的那一半
                version = version.split('-', 1)[1]

            if version:
                return version

    return None


def loader_version_from_disk(*roots: Path, loader: LoaderType) -> str | None:
    """在实例目录与仓库的 libraries 目录中查找加载器的最高版本号"""
    def sort_key(version: str):
        return [int(part) if part.isdigit() else part for part in re.split(r'[.\-+]', version)]

    for root in roots:
        for pattern in _LOADER_DIR_PATTERNS[loader]:
            directory = root / pattern

            if not directory.is_dir():
                continue

            try:
                versions = [entry.name for entry in directory.iterdir() if entry.is_dir()]
            except OSError:
                continue

            if versions:
                return max(versions, key=sort_key)

    return None


# 发布时间匹配时允许的误差
_RELEASE_TIME_TOLERANCE = timedelta(minutes=2)


def version_candidate(value) -> str | None:
    """
    判断一个字符串是否可以当作原版版本号, 是则返回它

    解析器会把所有无法识别的字符串都归为 ``april fool``, 因此这里要求版本号必须能解析出
    具体结构 (主次版本号、快照年份, 或带前缀的愚人节版本号), 避免把整合包名称当成版本。
    """
    if not isinstance(value, str) or not value.strip():
        return None

    value = value.strip()

    try:
        parsed = MinecraftVersion.from_string(value)
    except Exception:
        return None

    if parsed.type == 'april fool':
        # 愚人节版本号都带有 1.RV / w 这样的特征, 单纯的名字不算
        if not _APRIL_FOOL_VERSION.fullmatch(value):
            return None

    elif parsed.type != 'old' and getattr(parsed, 'major', None) is None and getattr(parsed, 'year', None) is None:
        return None

    return value


def version_from_release_time(
        raw: dict,
        candidates: dict[str, datetime | None],
) -> tuple[str, str] | None:
    """
    通过发布时间匹配原版版本号

    PCL 等启动器写出的描述文件会原样保留它所基于的原版版本的发布时间,
    连加载器实例也不例外 (加载器只改动 content, 不改 releaseTime)。
    因此发布时间是与原版版本号一一对应的可靠依据。

    :param raw: 已经规范化的版本 JSON
    :param candidates: 本地已知的 版本号 -> 发布时间
    :return: (版本号, 依据) 或 None
    """
    published = raw.get('releaseTime')

    if not isinstance(published, datetime):
        return None

    if published.tzinfo is not None:
        published = published.astimezone(timezone.utc).replace(tzinfo=None)

    exact = [
        version
        for version, other in candidates.items()
        if other is not None and abs(other - published) <= _RELEASE_TIME_TOLERANCE
    ]

    if len(exact) == 1:
        return exact[0], 'release-time'

    if len(exact) > 1:
        # 同一时刻有多个候选时, 优先取正式版
        releases = [
            v for v in exact
            if MinecraftVersion.from_string(v).type == 'release'
        ]

        if len(releases) == 1:
            return releases[0], 'release-time'

        if releases:
            return releases[0], 'release-time'

    return None


def iter_local_versions(instance_path: Path | str) -> dict[str, datetime | None]:
    """
    收集本储存库中已知的原版版本号及其发布时间

    本启动器安装的实例会把自己对应的原版发布时间写进描述文件, 因此可以据此建立索引,
    用于推断那些名称不包含版本号的第三方实例。

    :param instance_path: ``versions`` 目录
    :return: 版本号 -> 该版本的原版发布时间 (未知时为 None)
    """
    known: dict[str, datetime | None] = {}
    instance_path = Path(instance_path)

    try:
        entries = list(instance_path.iterdir())
    except OSError:
        return known

    for entry in entries:
        if not entry.is_dir():
            continue

        raw = None

        for json_name in (f'{entry.name}.json', 'version.json'):
            path = entry / json_name
            if path.is_file():
                try:
                    raw = msgspec.json.decode(path.read_bytes())
                except (OSError, ValueError):
                    raw = None

                if isinstance(raw, dict):
                    break

        if not isinstance(raw, dict):
            continue

        version = (
            version_candidate(raw.get('clientVersion'))
            or version_candidate(raw.get('id'))
        )

        if version is None:
            continue

        published = raw.get('releaseTime')
        if isinstance(published, str):
            try:
                published = msgspec.convert(published, datetime)
            except msgspec.ValidationError:
                published = None

        if isinstance(published, datetime) and published.tzinfo is not None:
            published = published.astimezone(timezone.utc).replace(tzinfo=None)

        # 同一版本可能被多个实例引用, 保留有发布时间的那个
        if version not in known or known[version] is None:
            known[version] = published if isinstance(published, datetime) else None

    return known


def pick_original_version_locally(
        raw: dict,
        candidates: dict[str, datetime | None] | None = None,
) -> tuple[str | None, str | None]:
    """
    不联网推断原版版本号

    只使用描述文件本身提供的信息, 依据的可靠性从高到低:

    1. ``clientVersion``: 第三方启动器明确记录它基于哪个原版版本;
    2. ``id`` 本身就是版本号;
    3. 发布时间与本储存库中某个已安装版本完全一致。

    实例名称不参与推断: 名称里的数字多半是整合包自身的版本号 (例如 ``New World 2.0``),
    据此猜测反而会引入错误。

    :return: (原版版本号, 推断依据)
    """
    for value in (version_candidate(raw.get('clientVersion')), version_candidate(raw.get('id'))):
        if value:
            return value, 'json'

    if candidates and (matched := version_from_release_time(raw, candidates)):
        return matched

    return None, None


# 联网推断时最多比对的候选版本数量
_ONLINE_MAX_CANDIDATES = 16

# 联网推断时同时发出的请求数量
_ONLINE_CONCURRENCY = 4


class VersionNotResolved(Exception):
    """本地无法可靠地确定原版版本号"""


async def pick_original_version_online(
        raw: dict,
        name: str,
        session,
        cache: dict | None = None,
) -> tuple[str | None, str | None]:
    """
    通过原版版本清单推断原版版本号

    官方清单只包含版本号与描述文件的地址, 因此还需要下载候选版本的描述文件来比对依赖库。
    为了控制耗时, 候选数量、并发数均有上限, 且整批实例共享 ``cache``:
    同一进程内的后续实例不会重复请求相同版本。

    只有"实例的依赖库完全覆盖某个原版版本"时才给出结论; 剩下的模糊匹配一律放弃,
    因为错误的版本号会让启动器选错资源索引与 Java 版本。

    :return: (原版版本号, 推断依据)
    """
    from app.third_party.mojang import MinecraftAPI

    if cache is None:
        cache = {}

    wanted = set(_library_names(raw))

    if not wanted:
        return None, None

    api = MinecraftAPI(session)

    if (cached := cache.get('manifest')) is None:
        cached = cache['manifest'] = await api.fetch_version_manifest()

    candidate_libraries: dict[str, set[str]] = cache.setdefault('libraries', {})

    pending = [
        entry
        for entry in _candidate_entries(name, cached)
        if entry.id not in candidate_libraries
    ]

    semaphore = asyncio.Semaphore(_ONLINE_CONCURRENCY)

    async def fetch(entry):
        async with semaphore:
            try:
                meta = await api.fetch_version_meta(entry.url)
            except Exception as exc:  # 单个版本失败不影响整体推断
                logger.debug("获取 {} 的版本描述失败: {}", entry.id, exc)
                return

            candidate_libraries[entry.id] = set(_library_names(msgspec.to_builtins(meta)))

    await asyncio.gather(*(fetch(entry) for entry in pending))

    exact = [
        (version, names)
        for version, names in candidate_libraries.items()
        if wanted.issubset(names)
    ]

    if not exact:
        return None, None

    # 加载器只会向原版依赖库追加内容, 因此取依赖库最多的那个
    best_version, _ = max(exact, key=lambda item: len(item[1]))
    return best_version, 'library-exact'


def _candidate_entries(name: str, manifest) -> list:
    """
    生成需要比对的候选版本条目

    名称中出现过的版本号优先, 其次是名称所暗示的大版本线附近的正式版。
    """
    candidates = []
    seen = set()

    def add(entry):
        if entry.id not in seen and len(candidates) < _ONLINE_MAX_CANDIDATES:
            seen.add(entry.id)
            candidates.append(entry)

    hint = version_from_name(name)

    if hint and (entry := manifest.find(hint)) is not None:
        add(entry)

        try:
            line = MinecraftVersion(hint).major
        except Exception:
            line = None

        if line is not None:
            # 名称里的版本号可能只是整合包版本, 因此同时看这一代的所有正式版
            for release in manifest.versions:
                if release.type != 'release':
                    continue

                try:
                    if MinecraftVersion(release.id).major == line:
                        add(release)
                except Exception:
                    continue

    for entry in manifest.versions:
        if entry.type == 'release':
            add(entry)

    return candidates


async def detect_loader_online(version: str, session) -> LoaderType | None:
    """通过网络确认某个原版版本是否有可用的加载器, 用于纠正误判"""
    from app.third_party.fabric_meta.api import FabricMetaV2

    try:
        api = FabricMetaV2(session)
        if await api.fetch_loaders_by_game(version):
            return 'fabric'
    except Exception as exc:
        logger.debug("检测 Fabric 加载器失败: {}", exc)

    return None


def resolve_client_jar(raw: dict, name: str, instance_path: Path, data_dir: Path | None) -> tuple[str, int | None]:
    """
    为客户端主文件找到本地文件, 并尽力补全它的大小

    第三方启动器写出的 JSON 往往没有 ``downloads.client.url`` (或者干脆没有 ``downloads``),
    此时只要本地存在主文件就不再依赖网络。PCL 之类的启动器还会把主文件链接到自己的缓存,
    链接目标丢失时仍然保留链接本身的位置。

    :return: (文件路径或下载地址, 文件大小), 大小无法确定时为 None
    """
    identifiers = {name, raw.get('id'), raw.get('clientVersion')}

    candidates = []

    for template in _CLIENT_JAR_CANDIDATES:
        for identifier in identifiers:
            if isinstance(identifier, str) and identifier:
                candidates.append(instance_path / template.format(name=name, id=identifier, mc=identifier))

    if data_dir is not None:
        version_dir = data_dir / 'versions'

        for identifier in identifiers:
            if isinstance(identifier, str) and identifier:
                candidates.append(version_dir / identifier / f'{identifier}.jar')

        # 某些启动器直接把主文件放在 versions/<名称>/ 下
        candidates.append(version_dir / name / f'{name}.jar')

    candidate_url = (raw.get('downloads') or {}).get('client', {}).get('url')
    broken_link: str | None = None

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue

        seen.add(candidate)

        try:
            if not candidate.is_file():
                continue
        except OSError:
            # 符号链接的目标不存在时会走到这里: 位置本身是对的, 只是目标丢失
            broken_link = broken_link or str(candidate)
            continue

        try:
            size = candidate.stat().st_size
        except OSError:
            size = 0

        if size > 0:
            return str(candidate), size

        broken_link = broken_link or str(candidate)

    if broken_link is not None:
        return broken_link, None

    if isinstance(candidate_url, str) and candidate_url:
        # JSON 自带下载地址, 不必依赖本地文件
        return candidate_url, None

    raise ClientJarNotResolved()


# ---------------------------------------------------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------------------------------------------------

async def build_version_meta(
        raw: dict,
        *,
        name: str,
        instance_path: Path,
        data_dir: Path | None = None,
        online: bool = True,
        session=None,
        cache: dict | None = None,
) -> tuple[VersionMeta, FixResult]:
    """
    由版本 JSON 生成启动器自己的元数据

    :param raw: 已经规范化的版本 JSON
    :param name: 实例名称
    :param instance_path: 实例目录
    :param data_dir: 第三方启动器的数据目录, 用于查找客户端主文件
    :param online: 是否允许联网推断
    :param session: 复用的网络会话
    :param cache: 整个批次共享的联网推断缓存, 避免为每个实例重复拉取
    :return: (元数据, 初步的修复结果)
    """
    from app.third_party.mojang.models import VersionMetaModel

    notes: list[str] = []
    result = FixResult(name=name, status=FixStatus.FIXED, notes=notes)

    model = msgspec.convert(raw, VersionMetaModel)
    meta = model.unify()

    # ------------------------------------------------------------------ 原版版本号
    # 发布时间索引对整个批次只需要建立一次
    if cache is not None:
        if (candidates := cache.get('release_times')) is None:
            candidates = cache['release_times'] = iter_local_versions(instance_path.parent)
    else:
        candidates = iter_local_versions(instance_path.parent)

    version, origin = pick_original_version_locally(raw, candidates)

    if version is None and online and session is not None:
        version, origin = await pick_original_version_online(raw, name, session, cache)

    if version is None:
        # 版本号决定资源索引与 Java 版本, 推测出来的值宁可不写
        raise VersionNotResolved(name)

    if version != meta.version:
        notes.append(tr("原版版本号推断为 {}", version))

    meta.version = version

    # ------------------------------------------------------------------ 加载器
    loader = detect_loader(raw)

    if loader is None and version is not None and online and session is not None:
        loader = await detect_loader_online(version, session)

    if loader is not None:
        meta.loader = loader
        notes.append(tr("推断为 {} 实例", loader))

        loader_version = (
            loader_version_from_disk(
                instance_path,
                instance_path.parent.parent,
                loader=loader,
            )
            or loader_version_from_libraries(raw, loader)
            or _loader_version_from_name(name, loader)
        )

        if loader_version is not None:
            meta.loader_version = loader_version

    # ------------------------------------------------------------------ 客户端主文件
    try:
        local_jar, size = resolve_client_jar(raw, name, instance_path, data_dir)
    except ClientJarNotResolved:
        local_jar, size = None, None

    client = meta.downloads.client

    if local_jar is not None:
        result.client_jar = local_jar

        is_local = not local_jar.startswith(('http://', 'https://'))

        if is_local:
            notes.append(tr("客户端主文件使用本地文件"))

            # 本地文件可用时就不再依赖网络, 缺失的地址与校验值留空
            client.url = client.url or ''
            client.sha1 = client.sha1 or ''

        elif not client.url:
            client.url = local_jar

        if size is not None and not client.size:
            client.size = size

    elif client.url:
        result.client_jar = client.url

    else:
        raise ClientJarNotResolved()

    result.version = version or meta.version
    result.loader = meta.loader
    result.loader_version = meta.loader_version
    return meta, result


async def fix_instance(
        instance,
        *,
        name: str | None = None,
        data_dir: Path | str | None = None,
        online: bool = True,
        force: bool = False,
        session=None,
        cache: dict | None = None,
) -> FixResult:
    """
    为单个实例补全缺失的 ``.mpk`` 描述文件

    :param instance: 实例目录对象
    :param name: 实例名称, 默认为目录名
    :param data_dir: 第三方启动器的数据目录, 用于查找客户端主文件
    :param online: 是否允许联网推断
    :param force: 是否覆盖已经存在的描述文件
    :param session: 复用的网络会话, 不提供时自动创建 (仅联网时)
    :param cache: 整个批次共享的联网推断缓存
    :return: 修复结果
    """
    from app.core.common import write_model

    name = name or instance.name
    instance_path = Path(instance.path)

    if instance.is_valid() and not force:
        return FixResult(name=name, status=FixStatus.SKIPPED, notes=[tr("已存在描述文件")])

    json_path = instance_path / f'{name}.json'

    if not json_path.is_file():
        return FixResult(name=name, status=FixStatus.FAILED, error=tr("缺少版本描述文件 {}.json", name))

    try:
        raw = msgspec.json.decode(json_path.read_bytes())
    except (ValueError, OSError) as exc:
        return FixResult(name=name, status=FixStatus.FAILED, error=tr("无法解析版本描述文件：{}", exc))

    if not isinstance(raw, dict):
        return FixResult(name=name, status=FixStatus.FAILED, error=tr("版本描述文件不是 JSON 对象"))

    notes: list[str] = []
    normalized = normalize_version_json(raw)

    own_session = False
    if online and session is None:
        from app.core.network import Session
        session = Session()
        own_session = True

    try:
        try:
            meta, result = await build_version_meta(
                normalized,
                name=name,
                instance_path=instance_path,
                data_dir=Path(data_dir) if data_dir else None,
                online=online,
                session=session,
                cache=cache,
            )
        except VersionNotResolved:
            return FixResult(
                name=name,
                status=FixStatus.FAILED,
                error=tr("无法推断原版版本号，已跳过以免写入错误的版本信息") + (
                    '' if online else tr("（可尝试加上 --online 联网推断）")
                ),
            )
        except ClientJarNotResolved:
            return FixResult(
                name=name,
                status=FixStatus.FAILED,
                error=tr("无法确定客户端主文件，请在实例目录中放置主文件，或使用 -d 指定第三方启动器的数据目录"),
            )
        except msgspec.ValidationError as exc:
            # 规范化之后依然无法解析, 退化为一份最小的可用描述
            logger.warning("实例 {!r} 的版本描述无法解析: {}", name, exc)

            try:
                meta, result = await build_version_meta(
                    rebuild_minimal_json(normalized.get('id') or name, notes),
                    name=name,
                    instance_path=instance_path,
                    data_dir=Path(data_dir) if data_dir else None,
                    online=False,
                    session=None,
                )
            except VersionNotResolved:
                return FixResult(
                    name=name,
                    status=FixStatus.FAILED,
                    error=tr("重建后的描述文件无法推断原版版本号，已跳过"),
                )
            except (msgspec.ValidationError, ClientJarNotResolved):
                return FixResult(name=name, status=FixStatus.FAILED, error=tr("无法解析版本描述文件：{}", exc))

        # 推断出的补充说明需要并入返回结果
        result.notes = [*notes, *result.notes]

        write_model(instance.meta_file, meta, encoder='msgpack')

    finally:
        if own_session and session is not None:
            await session.close()

    return result
