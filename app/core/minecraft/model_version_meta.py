from datetime import datetime
from string import Template

from msgspec import Struct, field

from app.core.minecraft.base_models import Downloads, Rule
from app.core.resources.base import RulesMatcher
from app.core.resources.libraries import Library


class AssetIndexStruct(Struct):
    id: str
    sha1: str
    size: int
    total_size: int = field(name='totalSize')
    url: str


class VersionDownloadsStruct(Struct):
    client: Downloads
    server: Downloads | None = None
    client_mappings: Downloads | None = None
    server_mappings: Downloads | None = None


class JavaVersionStruct(Struct):
    component: str
    major_version: int = field(name='majorVersion')


class LibraryDownloadsStruct(Downloads):
    path: str


# class LibraryClassifiersStruct(Struct):
#     linux: LibraryDownloadsStruct | None = field(default=None, name='natives-linux')
#     windows: LibraryDownloadsStruct | None = field(default=None, name='natives-windows')
#     osx: LibraryDownloadsStruct | None = field(default=None, name='natives-osx')
#
#     def get(self, name) -> LibraryDownloadsStruct | None:
#         return getattr(self, name)


class LibraryExtractStruct(Struct):
    exclude: list[str]


class LibraryMultiDownloadsStruct(Struct):
    artifact: LibraryDownloadsStruct | None = None
    classifiers: dict[str, LibraryDownloadsStruct] | None = None


class LibraryStruct(Struct):
    downloads: LibraryMultiDownloadsStruct
    name: str
    rules: list[Rule] | None = None
    extract: LibraryExtractStruct | None = None
    natives: dict[str, str] | None = None

    @property
    def is_native(self):
        return bool(self.natives or Library(self.name).classifier)

    def match(self, matcher):
        return not self.rules or matcher.match(self.rules)

    def collect_files(self, matcher):
        d = self.downloads
        if self.rules and not matcher.match(self.rules):
            return

        else:
            if d.artifact:
                yield d.artifact

            if self.is_native and (classifier_dl := d.classifiers.get(matcher.os_name)):
                yield classifier_dl


class LoggingFileStruct(Downloads):
    id: str


class LoggingClientStruct(Struct):
    argument: str
    file: LoggingFileStruct
    type: str


class LoggingStruct(Struct):
    client: LoggingClientStruct


class ArgumentsRuleStruct(Struct):
    rules: list[Rule]
    value: str | list[str]


class ArgumentsStruct(Struct):
    game: list[str | ArgumentsRuleStruct]
    jvm: list[str | ArgumentsRuleStruct]


class VersionMetaModel(Struct):
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

    def format_game_args(self, env, matcher):
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

    def format_jvm_args(self, env, matcher):
        """
        格式化 JVM 参数，返回一个列表或者 None
        只有当版本元数据文件中不包含新版本的 arguments 字段时，函数返回 None

        :param env: 环境变量
        :param matcher: 规则匹配器
        :return: list or None
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

    def get_required_libraries(self, matcher):
        """
        返回所有当前系统需要的依赖库

        :param matcher: 规则匹配器
        :return: 一个列表，包括所有在这个平台上游戏需要的依赖库的 LibraryStruct 对象
        """
        return [
            lib
            for lib in self.libraries
            if lib.match(matcher)
        ]

    def get_unzip_required_libraries(self, matcher: RulesMatcher):
        """
        返回所有需要解压的库

        :param matcher: 规则匹配器
        :return: 一个列表，包含所有需要解压的库对应的 LibraryStruct 对象
        """

        return [
            lib
            for lib in self.libraries
            if lib.extract and lib.match(matcher)
        ]