# version_meta.py
# Doc by DeepSeek
import datetime
from typing import Literal

import msgspec

from app.core.common import template_fill
from app.core.models.env import Environment


class Rule(msgspec.Struct, kw_only=True):
    """
    规则类，用于条件判断。

    用于控制库文件或参数在特定环境下是否生效。

    :ivar os: 操作系统匹配条件，键为系统属性名，值为期望值
    :ivar features: 功能特性匹配条件，键为特性名，值为期望布尔值
    """
    action: bool
    os: dict[str, str] | None = None
    features: dict[str, bool] | None = None


type Rules = list[Rule]
"""规则列表类型，包含多个 Rule 对象，用于复杂的条件判断。"""

type _LibraryStruct = DependenciesStruct.LibraryStruct

class BaseFileStruct(msgspec.Struct, kw_only=True):
    url: str
    sha1: str
    size: int

class DependenciesStruct(msgspec.Struct):
    """
    依赖结构体，包含库文件和资源文件信息。

    :param libraries: 库文件列表
    :param assets: 资源文件列表
    """

    class LibraryStruct(msgspec.Struct):
        """
        库文件结构体。

        :param name: Maven 格式的库名称（group:artifact:version）
        :param path: 库文件在仓库中的路径
        :param sha1: 库文件的 SHA1 哈希值
        :param size: 库文件大小（字节）
        :param maven_url: Maven 仓库 URL
        """
        name: str
        path: str
        sha1: str
        size: int

        maven_url: str  # Maven 仓库 URL

    class CommonLibraryStruct(msgspec.Struct, kw_only=True, tag='common'):
        artifact: _LibraryStruct
        rules: Rules | None = None

    class NativeLibraryStruct(msgspec.Struct, kw_only=True, tag='native'):
        """
        原生库文件结构体，用于平台相关的本地库。

        :param artifact: 通用的库文件，可能不存在
        :param natives: 本地库映射，键为环境标识（name, arch or None, version or None），值为对应的库文件
        :param rules: 规则列表，控制在不同环境是否需要该库
        """
        artifact: _LibraryStruct | None = None  # 通用的库文件，可能不存在
        natives: dict[str, str]  # 本地库，格式与 mojang 一致
        classifiers: dict[str, _LibraryStruct]
        rules: Rules | None = None  # 规则，与 mojang 的格式一致，控制在不同环境是否需要

        def get_classifier(self, env: Environment):
            pattern = self.natives[env.os_name]
            return template_fill(
                pattern, env.to_dict()
            )

        def get_native(self, env: Environment):
            classifier = self.get_classifier(env)
            return classifier, self.classifiers[classifier]


    class AssetsIndexStruct(BaseFileStruct, kw_only=True, gc=False):
        id: str
        total_size: int

    libraries: list[CommonLibraryStruct | NativeLibraryStruct]
    assets_index: AssetsIndexStruct


class ArgumentsStruct(msgspec.Struct):
    """
    启动参数结构体。

    包含游戏和 JVM 的启动参数，支持条件规则。

    :param game: 游戏启动参数列表
    :param jvm: JVM 启动参数列表
    """

    class RuleArg(msgspec.Struct):
        """
        带规则的参数项。

        :param rules: 规则列表，控制该参数在何种条件下生效
        :param value: 参数值，可以是字符串或字符串列表
        """
        rules: Rules
        value: str | list[str]

    game: list[str | RuleArg]
    jvm: list[str | RuleArg]

class DownloadsStruct(msgspec.Struct, kw_only=True, gc=False):
    client: BaseFileStruct
    server: BaseFileStruct | None = None

class VersionMeta(msgspec.Struct, kw_only=True):
    """
    游戏版本元数据。

    包含 Minecraft 版本的所有信息，包括版本号、依赖、启动参数等。

    :param version: 版本号（如 "1.20.4"）
    :param type: 版本类型，'snapshot'（快照版）或 'release'（正式版）
    :param release_time: 发布时间
    :param loader: 模组加载器类型，'forge' 或 'fabric'，默认为 None
    :param loader_version: 模组加载器版本号，默认为 None
    :param dependencies: 依赖信息（库和资源）
    :param main_class: Java 主类名
    :param arguments: 启动参数
    """
    # 基本信息
    # - 版本版本号
    version: str
    type: Literal['snapshot', 'release']
    release_time: datetime.datetime

    # - 加载器信息
    loader: Literal['forge', 'fabric',] | None = None
    loader_version: str | None = None

    # 文件信息
    # - 依赖库
    dependencies: DependenciesStruct
    # - 客户端/服务端主文件
    downloads: DownloadsStruct

    # 启动信息
    # - 主类
    main_class: str
    # - 参数
    arguments: ArgumentsStruct
