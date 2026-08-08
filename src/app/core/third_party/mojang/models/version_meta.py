"""
版本元数据模型模块。

定义了 Minecraft 版本 JSON 文件的完整数据结构，包括版本信息、依赖库、
启动参数、资源索引等。
"""
import shlex
import typing
from datetime import datetime

import msgspec
from msgspec import Struct, field

from app.core.minecraft.base_models import Downloads, Rule
from app.core.models.version_meta import VersionMeta, DependenciesStruct
from app.core.third_party.mojang.models import AssetIndexModel

if typing.TYPE_CHECKING:
    from app.core.minecraft.matcher import RulesMatcher

from app.core.models.library import Library


class AssetIndexStruct(Downloads):
    """
    版本的资源文件索引下载信息。
    相对于普通的 Downloads 结构，它多了 `id` 和 `total_size` 字段。

    :ivar id: 资源索引的唯一标识符
    :ivar total_size: 该索引包含的所有资源文件的总大小
    """
    id: str
    total_size: int = field(name='totalSize')


class VersionDownloadsStruct(Struct):
    """
    每一个游戏版本的下载信息。

    :ivar client: 客户端下载信息
    :ivar server: 服务端下载信息，该字段在某些旧版本中可能不存在
    :ivar client_mappings: 客户端的名称混淆映射文件下载信息，该字段在某些旧版本中可能不存在
    :ivar server_mappings: 服务端的名称混淆映射文件下载信息，该字段在某些旧版本中可能不存在
    """
    client: Downloads
    server: Downloads | None = None
    client_mappings: Downloads | None = None
    server_mappings: Downloads | None = None


class JavaVersionStruct(Struct):
    """
    Java 运行时需求信息。

    :ivar component: Java 运行时的组件类型（如 "jre-legacy" 或 "jre"）
    :ivar major_version: Java 运行时所需的最低主版本号
    """
    component: str
    major_version: int = field(name='majorVersion')


class LibraryDownloadsStruct(Downloads):
    """
    库的通用下载信息结构。
    它比普通的下载信息结构多一个 `path` 字段。

    :ivar path: 文件在 libraries 文件夹中的相对路径
    """
    path: str


class LibraryExtractStruct(Struct):
    """
    远古版本遗留的解压配置结构。
    用于指定在解压库文件时需要排除的目录。

    :ivar exclude: 解压时需要排除的文件夹名称列表
    """
    exclude: list[str]


class LibraryMultiDownloadsStruct(Struct):
    """
    每一个库的 `.downloads` 字段结构。

    :ivar artifact: 通用库文件下载信息，某些旧版本中该字段可能为空
    :ivar classifiers: 分类库文件下载表（如按操作系统区分的 native 库）
    """
    artifact: LibraryDownloadsStruct | None = None
    classifiers: dict[str, LibraryDownloadsStruct] | None = None


class StandardLibraryStruct(Struct):
    """
    单个依赖库（Library）的完整结构定义。

    :ivar downloads: 库文件的下载信息
    :ivar name: 库的完整 Maven 坐标（groupId:artifactId:version）
    :ivar rules: 该库适用的规则列表，用于判断库是否在特定平台生效
    :ivar extract: 解压配置（仅远古版本使用）
    :ivar natives: 原生库映射，键为操作系统名，值为对应的 classifier
    """
    downloads: LibraryMultiDownloadsStruct
    name: str
    rules: list[Rule] | None = None
    extract: LibraryExtractStruct | None = None
    natives: dict[str, str] | None = None

    @property
    def is_native(self) -> bool:
        """
        判断该库是否为原生库（Native Library）。

        只要包含 `natives` 字段或者库名中包含 classifier 的，都被视为原生库。
        如需仅检查旧版 natives 定义，可直接判断 `.natives` 是否为空。

        :return: 如果是原生库则返回 True，否则返回 False
        """
        return bool(self.natives or Library(self.name).classifier)

    def match(self, matcher: RulesMatcher) -> bool:
        """
        通过传入的规则匹配器判断该库是否在当前平台上被需要。

        :param matcher: 规则匹配器实例，用于评估 `rules` 列表
        :return: 如果该库在当前平台需要被使用则返回 True，否则返回 False
        """
        return not self.rules or matcher.match(self.rules)

    def collect_files(self, matcher: RulesMatcher | None = None, env: dict[str, str] | None = None):
        """
        收集该库在当前平台上所有需要下载的文件。

        包括通用库文件和针对当前操作系统的原生库文件。
        如果该库在当前平台不被需要，则不会产生任何产出。

        :param matcher: 规则匹配器实例，为空表示不进行匹配
        :param env: 环境信息，不提供则自动从 matcher 中提取

        """
        d = self.downloads
        if matcher and self.rules and not matcher.match(self.rules):
            return

        env = env or matcher.env

        if d.artifact:
            yield d.artifact, self.name

        if self.natives:
            from app.core.common import template_fill
            classifier = template_fill(self.natives[env['os']], env)
            yield d.classifiers[classifier], f'{self.name}:{classifier}'


class FabricLibraryStruct(Struct):
    """
    Fabric 专用的库结构

    :ivar name: 库的 maven 坐标
    :ivar url: maven 仓库的 base_url

    :ivar md5: 文件的 MD5 校验值，可能不存在
    :ivar sha1: 文件的 SHA-1 校验值，可能不存在
    :ivar sha256: 文件的 SHA-256 校验值，可能不存在
    :ivar sha512: 文件的 SHA-512 校验值，可能不存在
    :ivar size: 文件的大小，可能不存在
    """
    name: str
    url: str

    md5: str | None = None
    sha1: str | None = None
    sha256: str | None = None
    sha512: str | None = None

    size: int | None = None

    def match(self, _):  # Fabric 的库没有 rules 这一说
        return True

    @property
    def checksum(self) -> tuple[str, str] | None:
        if self.sha1:  # sha1 优先，毕竟 Mojang 一致用的 sha1
            return 'sha1', self.sha1
        elif self.sha256:
            return 'sha256', self.sha256
        elif self.sha512:
            return 'sha512', self.sha512
        elif self.md5:
            return 'md5', self.md5
        else:
            return None


class LoggingFileStruct(Downloads):  # TODO
    """
    日志配置文件的下载信息。

    :ivar id: 日志配置文件的唯一标识符
    """
    id: str


class LoggingClientStruct(Struct):
    """
    日志配置客户端子结构，位于 `.logging.client` 字段。

    :ivar argument: 启用该日志配置文件所需的 JVM 参数
    :ivar file: 日志配置文件的下载信息
    :ivar type: 日志配置文件的格式类型（如 "log4j2"）
    """
    argument: str
    file: LoggingFileStruct
    type: str


class LoggingStruct(Struct):
    """
    版本日志配置的根结构。

    :ivar client: 客户端日志配置信息
    """
    client: LoggingClientStruct


class ArgumentsRuleStruct(Struct):
    """
    带规则的条件参数结构。

    用于表示仅在特定条件下生效的启动参数。

    :ivar rules: 该参数生效的规则列表
    :ivar value: 参数的值，可以是单个字符串或字符串列表
    """
    rules: list[Rule]
    value: str | list[str]


class ArgumentsStruct(Struct):
    """
    版本启动参数结构（现代版本格式）。

    替代旧的 `minecraftArguments` 字段。

    :ivar game: 游戏引擎参数列表
    :ivar jvm: JVM 启动参数列表
    """
    game: list[str | ArgumentsRuleStruct]
    jvm: list[str | ArgumentsRuleStruct]


class VersionMetaModel(Struct):
    """
    游戏版本元数据模型。

    对应 Minecraft 官方 Launcher Meta 中的版本 JSON 文件结构。

    :ivar assets: 资源索引的 ID（如 "1.16"）
    :ivar asset_index: 资源索引文件的下载信息
    :ivar compliance_level: Java 合规级别
    :ivar downloads: 客户端/服务端 jar 文件的下载信息
    :ivar id: 版本 ID（如 "1.20.4"）
    :ivar java_version: Java 运行时版本要求
    :ivar libraries: 该版本所需的所有依赖库列表
    :ivar logging: 日志配置文件信息
    :ivar main_class: 游戏主类名称
    :ivar minimum_launcher_version: 启动器所需的最低版本号
    :ivar release_time: 版本发布时间
    :ivar time: 版本元数据更新时间
    :ivar type: 版本类型（如 "release"、"snapshot" 或 "old_alpha"）
    """
    assets: str
    asset_index: AssetIndexStruct = field(name='assetIndex')
    compliance_level: int = field(name='complianceLevel')
    downloads: VersionDownloadsStruct
    id: str
    java_version: JavaVersionStruct = field(name='javaVersion')
    raw_libraries: list[dict] = field(name='libraries')
    logging: LoggingStruct
    main_class: str = field(name='mainClass')
    minimum_launcher_version: int = field(name='minimumLauncherVersion')
    release_time: datetime = field(name='releaseTime')
    time: datetime
    type: str

    _legacy_arguments: str | None = field(default=None, name='minecraftArguments')
    _modern_arguments: ArgumentsStruct | None = field(default=None, name='arguments')

    def unify(self) -> VersionMeta:
        from app.core.models.version_meta import DependenciesStruct, Rule as R
        D = DependenciesStruct

        def unify_libraries():
            def unify_standard(__lib: dict):
                lib = msgspec.convert(__lib, type=StandardLibraryStruct)
                if lib.natives:
                    artifact = lib.downloads.artifact
                    return D.NativeLibraryStruct(
                        artifact=(
                            D.LibraryStruct(
                                lib.name,
                                artifact.path,
                                sha1=artifact.sha1,
                                size=artifact.size,
                                maven_url="https://libraries.minecraft.net"
                            )

                            if artifact else None
                        ),
                        natives=lib.natives,  # type: ignore
                        classifiers={
                            k: D.LibraryStruct(
                                name=f'{lib.name}:{k}',
                                path=v.path,
                                size=v.size,
                                sha1=v.sha1,
                                maven_url="https://libraries.minecraft.net"
                            )
                            for k, v in lib.downloads.classifiers.items()  # type: ignore
                        }
                    )
                else:
                    artifact = lib.downloads.artifact
                    _ = D.LibraryStruct(
                        name=lib.name,
                        path=artifact.path,
                        sha1=artifact.sha1,
                        size=artifact.size,
                        maven_url="https://libraries.minecraft.net"
                    )
                    return D.CommonLibraryStruct(
                        artifact=_,
                        rules=[
                            R(
                                action=i.action == 'allow',
                                os=i.os,
                                features=i.features,
                            )
                            for i in lib.rules
                        ] if lib.rules else None
                    )

            def unify_fabric(__lib: dict):
                lib = msgspec.convert(__lib, type=FabricLibraryStruct)
                l = Library(lib.name)
                return D.LibraryStruct(
                    name=lib.name,
                    path=l.path,
                    sha1=lib.sha1,  # 虽然定义模型时提到 sha1 等字段可能不存在，然而从 meta.fabricmc.net 抓下来的信息都会包含
                    size=lib.size,
                    maven_url=lib.url
                )

            return [
                (
                    unify_standard(lib)  # 实际上 Forge 和 Standard 是合并的，Forge 采用和 Mojang 相同的格式储存依赖库
                    if 'url' not in lib
                    else
                    unify_fabric(lib)
                )

                for lib in self.raw_libraries
            ]

        def unify_arguments():
            from app.core.models.version_meta import ArgumentsStruct as CoreArgumentsStruct, Rule as CoreRule
            A = CoreArgumentsStruct

            def unify_argument_list(lst):
                return [
                    i if isinstance(i, str) else CoreArgumentsStruct.RuleArg(i.rules, i.value)
                    for i in lst
                ]

            if self._modern_arguments:
                return CoreArgumentsStruct(
                    unify_argument_list(self._modern_arguments.game),
                    unify_argument_list(self._modern_arguments.jvm)
                )
            else:
                arg_strips = shlex.split(self._legacy_arguments)  # type: ignore
                return CoreArgumentsStruct(
                    game=arg_strips,
                    jvm=[
                        "-Dorg.lwjgl.librarypath=${natives_directory}",
                        "-Djava.library.path=${natives_directory}",
                        '-cp', "${classpath}",
                        A.RuleArg(
                            [
                                CoreRule(
                                    os={
                                        'name': 'osx',
                                    },
                                    action=True
                                )
                            ],
                            value='-XstartOnFirstThread'
                        ),
                        A.RuleArg(
                            [
                                CoreRule(
                                    os={
                                        'arch': "x86",
                                    },
                                    action=True
                                )
                            ],
                            value='-Xss1M'
                        )
                    ]
                )

        from app.core.models.version_meta import DownloadsStruct as F, BaseFileStruct as B

        index = self.asset_index
        return VersionMeta(
            version=self.id,
            type='release' if self.type == 'release' else 'snapshot',
            release_time=self.release_time,
            dependencies=DependenciesStruct(
                unify_libraries(),
                msgspec.convert(index, D.AssetsIndexStruct, from_attributes=True)
            ),
            main_class=self.main_class,
            arguments=unify_arguments(),
            downloads=F(
                client=B(
                    url=self.downloads.client.url,
                    sha1=self.downloads.client.sha1,
                    size=self.downloads.client.size,
                ),
                server=B(
                    url=self.downloads.server.url,
                    sha1=self.downloads.server.sha1,
                    size=self.downloads.server.size
                ) if self.downloads.server else None
            )
        )
