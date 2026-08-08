# server_meta.py
# Doc by DeepSeek
from uuid import UUID

import msgspec

from app.core.minecraft.text_component import TextComponent


class SinglePlayerStruct(msgspec.Struct):
    """
    单个玩家信息结构体。

    :param name: 玩家名称
    :param id: 玩家 UUID
    """
    name: str
    id: UUID


class PlayersStruct(msgspec.Struct):
    """
    服务器玩家信息结构体。

    :param max: 最大玩家数量
    :param online: 当前在线玩家数量
    :param sample: 在线玩家样本列表
    """
    max: int
    online: int
    sample: list[SinglePlayerStruct]


class VersionStruct(msgspec.Struct):
    """
    服务器版本信息结构体。

    :param name: 版本名称（如 "1.20.4"）
    :param protocol: 协议版本号
    """
    name: str
    protocol: int


def fix_text_component(component: dict):
    """
    修复文本组件字典，确保包含 'type' 字段并递归处理 'extra' 字段。

    :param component: 文本组件字典
    """
    component.setdefault('type', 'text')
    for item in component.get('extra', ()):
        if isinstance(item, dict):
            fix_text_component(item)


class ServerMeta(msgspec.Struct):
    """
    服务器元数据结构体。

    包含服务器状态查询响应的所有信息，包括玩家列表、版本和描述。

    :param players: 玩家信息
    :param version: 版本信息
    :param _description: 服务器描述（原始数据，可能为字符串或字典）
    """
    players: PlayersStruct
    version: VersionStruct
    _description: str | dict | None = msgspec.field(name='description', default=None)

    @property
    def description(self) -> str | TextComponent | None:
        """
        获取服务器描述。

        如果描述为字符串则直接返回，如果为字典则转换为 TextComponent 对象。

        :return: 服务器描述字符串、TextComponent 对象或 None
        """
        if self._description is None or isinstance(self._description, str):
            return self._description
        else:
            fix_text_component(self._description)
            return msgspec.convert(self._description, TextComponent)