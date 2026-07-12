"""
启动上下文模块。

定义了 Minecraft 启动所需的所有上下文信息，包括用户认证、游戏配置、
JVM 参数等。
"""

import dataclasses
import json
from uuid import UUID

import msgspec


@dataclasses.dataclass(slots=True, kw_only=True)
class LaunchContext:
    """
    Minecraft 启动上下文。

    包含启动游戏所需的所有配置信息，包括用户信息、游戏目录、认证信息、
    窗口设置、快速启动配置等。

    :ivar username: 玩家用户名
    :ivar version_name: 游戏版本名称（如 "1.20.4"）
    :ivar version_type: 游戏版本类型（如 "release"、"snapshot"）
    :ivar user_properties: 用户自定义属性字典
    :ivar user_type: 用户类型，默认为 'legacy'
    :ivar game_dir: 游戏根目录路径
    :ivar assets_dir: 资源文件目录路径
    :ivar assets_index_name: 资源索引名称
    :ivar uuid: 玩家 UUID
    :ivar token: 认证令牌
    :ivar clientid: 客户端 ID
    :ivar xuid: Xbox 用户 ID
    :ivar width: 游戏窗口宽度
    :ivar height: 游戏窗口高度
    :ivar quick_play_path: 快速启动配置路径
    :ivar quick_play_single_player: 快速启动单人游戏的世界名称
    :ivar quick_play_multi_player: 快速启动多人游戏的服务器地址
    :ivar quick_play_realms: 快速启动 Realms 的 ID
    :ivar natives_dir: 原生库文件目录路径
    :ivar classpath: Java 类路径
    :ivar launcher_name: 启动器名称
    :ivar launcher_version: 启动器版本号
    """
    # Basic
    username: str
    version_name: str
    version_type: str

    user_properties: dict = dataclasses.field(default_factory=dict)
    user_type: str = 'legacy'

    # Resources
    game_dir: str
    assets_dir: str
    assets_index_name: str

    # Auth
    uuid: str | UUID
    token: str
    clientid: str
    xuid: str

    # Customs

    # 1. window size
    width: int | None = None
    height: int | None = None

    # 2. quick play
    quick_play_path: str | None = None

    # for single player
    quick_play_single_player: str | None = None

    # for multi-player
    quick_play_multi_player: str | None = None

    # for realms
    quick_play_realms: str | None = None

    # 3. JVM Contexts
    natives_dir: str
    classpath: str

    # 4. Launcher info
    launcher_name: str
    launcher_version: str

    def to_dict(self) -> dict:
        """
        将启动上下文转换为环境变量字典。

        转换后的字典可用于替换 Minecraft 启动命令中的占位符（如 ${auth_player_name}）。

        :return: 键为占位符名称，值为对应内容的字典
        """
        return {
            'auth_player_name': self.username,
            'version_name': self.version_name,
            'version_type': self.version_type,

            'user_type': self.user_type,
            'user_properties': json.dumps(self.user_properties),

            'game_directory': self.game_dir,
            'assets_root': self.assets_dir,
            'assets_index_name': self.assets_index_name,

            'auth_uuid': self.uuid,
            'auth_access_token': self.token,
            'clientid': self.clientid,
            'auth_xuid': self.xuid,

            'resolution_width': self.width,
            'resolution_height': self.height,

            'quick_play_path': self.quick_play_path,
            'quick_play_single_player': self.quick_play_single_player,
            'quick_play_multi_player': self.quick_play_multi_player,
            'quick_play_realms': self.quick_play_realms,

            'natives_directory': self.natives_dir,
            'classpath': self.classpath,

            'launcher_name': self.launcher_name,
            'launcher_version': self.launcher_version,

        }


@dataclasses.dataclass(slots=True, kw_only=True)
class BasicJVMContext:
    """
    基础 JVM 配置上下文。

    定义 Java 虚拟机的内存分配和垃圾回收器配置。

    :ivar mem_min: 初始堆内存大小（如 "512M"、"2G"）
    :ivar mem_max: 最大堆内存大小（如 "2048M"、"4G"）
    :ivar gc: 垃圾回收器类型，可选 'ZGC'、'G1GC'、'CMS'、'Serial'、'Parallel'，默认为 'ZGC'
    """
    mem_min: str
    mem_max: str
    gc: str = 'ZGC'

    def to_args(self) -> list[str]:
        """
        将 JVM 配置转换为 Java 命令行参数列表。

        :return: JVM 参数列表，如 ['-Xms512M', '-Xmx2048M', '-XX:+UseZGC']
        """
        gc_flags = {
            'ZGC': ['-XX:+UseZGC'],
            'G1GC': ['-XX:+UseG1GC'],
            'CMS': ['-XX:+UseConcMarkSweepGC'],
            'Serial': ['-XX:+UseSerialGC'],
            'Parallel': ['-XX:+UseParallelGC'],
        }

        return [
            '-Xms' + self.mem_min,
            '-Xmx' + self.mem_max,
            *gc_flags.get(self.gc.upper(), [f'-{self.gc}'])
        ]