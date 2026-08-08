"""
Minecraft 核心数据模型。

定义了 Minecraft 启动器和版本解析中通用的基础数据结构。
"""

from typing import Literal

from msgspec import Struct


class Downloads(Struct):
    """
    基础下载信息结构。

    表示一个可通过 URL 下载的文件的基本元数据。

    :ivar sha1: 文件的 SHA-1 校验值，用于验证文件完整性
    :ivar size: 文件大小（单位：字节）
    :ivar url: 文件的下载地址
    """
    sha1: str
    size: int
    url: str


class Rule(Struct):
    """
    规则结构，用于条件判断。

    用于定义某个功能或组件在特定条件下是否启用。
    支持基于操作系统和特性的规则匹配。

    :ivar action: 匹配成功时的动作，'allow' 表示允许，'disallow' 表示禁止
    :ivar os: 操作系统匹配条件，如 {"name": "windows"}，为空时表示匹配所有系统
    :ivar features: 特性匹配条件，键为特性名称，值为是否启用
    """
    action: Literal['allow', 'disallow']
    os: dict[str, str] | None = None
    features: dict[str, bool] | None = None