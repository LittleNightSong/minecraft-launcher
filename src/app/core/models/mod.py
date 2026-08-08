from typing import Literal

import msgspec


class Dependency(msgspec.Struct):
    """
    模组依赖信息元数据

    :ivar id: 所依赖的模组 ID
    :ivar version_range: 依赖的版本区间字符串表达（或是包含它的列表）
    :ivar environment: 依赖环境，在哪个环境下需要这个依赖
    :ivar reason: 原因，当依赖不符合时提供给用户的参考原因
    """
    id: str
    version_range: str | list[str]
    environment: Literal["server", "client", "all"]
    reason: str | None = None


class ModMeta(msgspec.Struct, kw_only=True):
    """
    模组元数据

    :ivar id: 模组的唯一标识符
    :ivar version: 模组的版本
    :ivar display_name: 显示名称
    :ivar description: 描述
    :ivar urls: 链接表
    :ivar icon: 图标文件的路径（相对于模组文件内部）
    :ivar environment: 模组的运行环境（ server, client, all）
    """
    id: str
    version: str
    display_name: str
    description: str

    icon: str | None = None

    urls: dict[str, str]

    environment: Literal["server", "client", "all"] = 'all'

    dependencies: list[Dependency]
    breaks: list[Dependency]
    provides: set[str] = msgspec.field(default_factory=set)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, o: object) -> bool:
        return isinstance(o, ModMeta) and self.id == o.id
