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

from app.third_party.mojang.models.base_models import Downloads, Rule

if typing.TYPE_CHECKING:
    from app.core.models.version_meta import VersionMeta
    from app.core.models.version_meta import Rule as CoreRule

from app.core.models import Library


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

    def unify(self, *, maven_url_getter=None):
        from app.core.models.version_meta import (
            LibraryStruct as CoreL,
            NativeLibraryStruct as CoreN,
            CommonLibraryStruct as CoreC
        )

        def get_maven_url(lib: LibraryDownloadsStruct):
            return lib.url.removesuffix(lib.path)

        get_maven_url = maven_url_getter or get_maven_url

        if self.natives:
            artifact = self.downloads.artifact
            return CoreN(
                artifact=(
                    CoreL(
                        self.name,
                        artifact.path,
                        sha1=artifact.sha1,
                        size=artifact.size,
                        maven_url=get_maven_url(artifact)
                    )

                    if artifact else None
                ),
                natives=self.natives,  # type: ignore
                classifiers={
                    classifier: CoreL(
                        name=f'{self.name}:{classifier}',
                        path=downloads.path,
                        size=downloads.size,
                        sha1=downloads.sha1,
                        maven_url=get_maven_url(downloads)
                    )
                    for classifier, downloads in self.downloads.classifiers.items()  # type: ignore
                },
                rules=_unify_rules(self.rules)
            )
        else:
            artifact = self.downloads.artifact
            assert artifact
            _ = CoreL(
                name=self.name,
                path=artifact.path,
                sha1=artifact.sha1,
                size=artifact.size,
                maven_url=get_maven_url(artifact)
            )
            return CoreC(
                artifact=_,
                rules=_unify_rules(self.rules)
            )

    @property
    def is_native(self) -> bool:
        """
        判断该库是否为原生库（Native Library）。

        只要包含 `natives` 字段或者库名中包含 classifier 的，都被视为原生库。
        如需仅检查旧版 natives 定义，可直接判断 `.natives` 是否为空。

        :return: 如果是原生库则返回 True，否则返回 False
        """
        return bool(self.natives or Library(self.name).classifier)


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

    def unify(self):
        from app.core.models.version_meta import ArgumentsStruct as CoreArgumentsStruct
        def unify_argument_list(lst):
            return [
                i if isinstance(i, str) else CoreArgumentsStruct.RuleArg(_unify_rules(i.rules), i.value)
                for i in lst
            ]

        return CoreArgumentsStruct(
            unify_argument_list(self.game),
            unify_argument_list(self.jvm)
        )


@typing.overload
def _unify_rules(rules: None) -> None:
    ...


@typing.overload
def _unify_rules(rules: list) -> list[CoreRule]:
    ...


def _unify_rules(rules):
    from app.core.models.version_meta import Rule as R
    return [
        R(
            action=i.action == 'allow',
            os=i.os,
            features=i.features,
        )
        for i in rules
    ] if rules else None


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
        from app.third_party.fabric_meta.models.v2 import LibraryStruct as _FabricLibraryStruct
        from app.core.models.version_meta import DependenciesStruct
        from app.core.models.version_meta import (
            LibraryStruct as CoreL,
            CommonLibraryStruct as CoreC,
            VersionMeta
        )
        D = DependenciesStruct

        def unify_libraries():
            def unify_standard(__lib: dict):
                lib = msgspec.convert(__lib, type=StandardLibraryStruct)
                return lib.unify()

            def unify_fabric(__lib: dict):
                lib = msgspec.convert(__lib, type=_FabricLibraryStruct)
                l = Library(lib.name)
                return CoreC(
                    artifact=CoreL(
                        name=lib.name,
                        path=str(l.path),
                        sha1=lib.sha1,  # 虽然定义模型时提到 sha1 等字段可能不存在，然而从 meta.fabricmc.net 抓下来的信息都会包含
                        size=lib.size,
                        maven_url=lib.maven_url
                    )
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

        def unify_legacy_arguments():
            from app.core.models.version_meta import ArgumentsStruct, Rule as R
            A = ArgumentsStruct

            arg_strips = shlex.split(self._legacy_arguments)  # type: ignore
            return ArgumentsStruct(  # 这是启动器内置的默认 jvm 参数
                # pyrefly: ignore [bad-argument-type]
                game=arg_strips,
                jvm=[
                    "-Dorg.lwjgl.librarypath=${natives_directory}",
                    "-Djava.library.path=${natives_directory}",
                    '-cp', "${classpath}",
                    A.RuleArg(
                        [
                            R(
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
                            R(
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

        from app.core.models.version_meta import (
            DownloadsStruct as F,
            BaseFileStruct as B,
            JavaDependencyStruct as J
        )

        index = self.asset_index
        return VersionMeta(
            version=self.id,
            type='release' if self.type == 'release' else 'snapshot',
            release_time=self.release_time,
            dependencies=DependenciesStruct(
                unify_libraries(),
                msgspec.convert(index, D.AssetsIndexStruct, from_attributes=True),
                J(
                    major=self.java_version.major_version
                )
            ),
            main_class=self.main_class,
            arguments=self._modern_arguments.unify() if self._modern_arguments else unify_legacy_arguments(),
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
