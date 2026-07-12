"""
版本元数据模型模块。

定义了 Minecraft 版本 JSON 文件的完整数据结构，包括版本信息、依赖库、
启动参数、资源索引等。
"""
import typing
from datetime import datetime
from string import Template

from msgspec import Struct, field

from app.core.minecraft.base_models import Downloads, Rule

if typing.TYPE_CHECKING:
    from app.core.resources.base import RulesMatcher
    from app.core.resources.libraries import Library


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


class LibraryStruct(Struct):
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

    def collect_files(self, matcher: RulesMatcher):
        """
        收集该库在当前平台上所有需要下载的文件。

        包括通用库文件和针对当前操作系统的原生库文件。
        如果该库在当前平台不被需要，则不会产生任何产出。

        :param matcher: 规则匹配器实例
        :yield: LibraryDownloadsStruct 对象，表示需要下载的库文件
        """
        d = self.downloads
        if self.rules and not matcher.match(self.rules):
            return

        else:
            if d.artifact:
                yield d.artifact

            if self.natives:
                yield d.classifiers[matcher.os_name]


class LoggingFileStruct(Downloads):
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
    libraries: list[LibraryStruct]
    logging: LoggingStruct
    main_class: str = field(name='mainClass')
    minimum_launcher_version: int = field(name='minimumLauncherVersion')
    release_time: datetime = field(name='releaseTime')
    time: datetime
    type: str

    _legacy_arguments: str | None = field(default=None, name='minecraftArguments')
    _modern_arguments: ArgumentsStruct | None = field(default=None, name='arguments')

    def format_game_args(self, env: dict, matcher: RulesMatcher) -> list[str] | str:
        """
        格式化游戏引擎启动参数。

        优先使用现代 `arguments.game` 格式，如果不存在则回退到旧版 `minecraftArguments`。
        所有参数中的占位符（如 `${auth_player_name}`）将使用 `env` 进行替换。

        :param env: 环境变量字典，用于替换参数模板中的占位符
        :param matcher: 规则匹配器，用于判断带规则的条件参数是否生效
        :return: 格式化后的参数列表（现代格式）或单个字符串（旧版格式）
        :raises ValueError: 当版本数据中既没有现代参数也没有旧版参数时抛出
        """
        if self._modern_arguments:
            g = self._modern_arguments.game
            args = []

            for arg in g:
                if isinstance(arg, str):
                    args.append(Template(arg).substitute(env))
                elif matcher.match(arg.rules):
                    if isinstance(arg.value, str):
                        args.append(Template(arg.value).substitute(env))

                    else:
                        args.extend([
                            Template(sub_arg).substitute(env)
                            for sub_arg in arg.value
                        ])

            return args

        elif self._legacy_arguments:
            return Template(self._legacy_arguments).substitute(env)

        else:
            raise ValueError("Cannot find any arguments")

    def format_jvm_args(self, env: dict, matcher: RulesMatcher) -> list[str] | None:
        """
        格式化 JVM 启动参数。

        仅当版本使用现代参数格式（包含 `arguments` 字段）时有效。
        旧版格式的版本不支持单独格式化 JVM 参数，将返回 None。

        :param env: 环境变量字典，用于替换参数模板中的占位符
        :param matcher: 规则匹配器，用于判断带规则的条件参数是否生效
        :return: 格式化后的 JVM 参数列表，若版本不支持则返回 None
        """
        if self._modern_arguments is None:
            return None

        args = []
        for arg in self._modern_arguments.jvm:
            if isinstance(arg, str):
                args.append(Template(arg).substitute(env))

            elif matcher.match(arg.rules):
                if isinstance(arg.value, str):
                    args.append(Template(arg.value).substitute(env))
                else:
                    args.extend([
                        Template(sub_arg).substitute(env)
                        for sub_arg in arg.value
                    ])

        return args

    def get_required_libraries(self, matcher: RulesMatcher) -> list[LibraryStruct]:
        """
        获取当前平台所需的所有依赖库。

        :param matcher: 规则匹配器实例
        :return: 在当前平台上需要使用的 LibraryStruct 对象列表
        """
        return [
            lib
            for lib in self.libraries
            if lib.match(matcher)
        ]

    def get_unzip_required_libraries(self, matcher: RulesMatcher) -> list[LibraryStruct]:
        """
        获取当前平台需要解压的依赖库。

        仅返回那些包含 `extract` 配置且在当前平台被需要的库。
        主要用于处理远古 Minecraft 版本中嵌套 JAR 的解压需求。

        :param matcher: 规则匹配器实例
        :return: 需要解压的 LibraryStruct 对象列表
        """
        return [
            lib
            for lib in self.libraries
            if lib.extract and lib.match(matcher)
        ]
