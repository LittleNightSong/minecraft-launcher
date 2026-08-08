# instance_meta.py
# Doc by DeepSeek
from typing import Literal


class InstanceConfig:
    """
    实例配置类（占位符）。

    用于存储 Minecraft 实例的自定义配置信息。
    具体字段待实现。
    """
    ...


class InstanceMeta:
    """
    Minecraft 实例元数据类。

    存储 Minecraft 游戏实例的基本信息，包括描述和自定义配置。

    :ivar description: 实例的描述信息
    :ivar config: 实例的自定义配置，默认为 None
    """
    # 基本信息
    description: str
    # 自定义配置
    config: InstanceConfig | None = None