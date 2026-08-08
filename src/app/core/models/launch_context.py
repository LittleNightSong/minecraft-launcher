# launch_context.py
# Doc by DeepSeek
"""
启动上下文模块。

定义了 Minecraft 启动所需的所有上下文信息，包括用户认证、游戏配置、
JVM 参数等。
"""

import dataclasses
import json
from pathlib import Path
from uuid import UUID


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
    :ivar libraries_directory: Forge 需要用到的环境变量之一，表示游戏储存库中 libraries 的位置
    :ivar classpath_sep: Forge 需要用到的环境变量之一，表示拼接 classpath 时使用的分隔符
    """
    # Basic
    username: str
    version_name: str
    version_type: str

    user_properties: dict = dataclasses.field(default_factory=dict)
    user_type: str = 'legacy'

    # Resources
    game_dir: str | Path
    assets_dir: str | Path
    assets_index_name: str

    # Auth
    uuid: str | UUID
    token: str

    # Infomation Share
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

    # 5. Forge Requirements
    libraries_directory: str | Path
    classpath_sep: str

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

            'quickPlayPath': self.quick_play_path,
            'quickPlaySingleplayer': self.quick_play_single_player,
            'quickPlayMultiplayer': self.quick_play_multi_player,
            'quickPlayRealms': self.quick_play_realms,

            'natives_directory': self.natives_dir,
            'classpath': self.classpath,

            'launcher_name': self.launcher_name,
            'launcher_version': self.launcher_version,

            'library_directory': self.libraries_directory,
            'classpath_separator': self.classpath_sep,
        }

    def generate_features(self):
        """
        生成 Minecraft 功能特性配置。

        :return: 功能特性字典
        """
        from ..minecraft.features import generate_features
        return generate_features(self)


import dataclasses
from typing import Generator


@dataclasses.dataclass(slots=True, kw_only=True)
class JVMContext:
    """
    基础 JVM 配置上下文。

    Editten by DeepSeek
    """
    mem_min: str | int | None = None
    mem_max: str | int | None = None
    gc: str | None = None

    system_properties: dict[str, str | int | bool] = dataclasses.field(default_factory=dict)
    non_standard_options: dict[str, str | bool] = dataclasses.field(default_factory=dict)
    high_level_options: dict[str, str | bool] = dataclasses.field(default_factory=dict)

    def _to_args(self) -> Generator[str, None, None]:
        """将 JVM 配置转换为 Java 命令行参数列表（生成器）。"""
        gc_flags = {
            'ZGC': ['-XX:+UseZGC'],
            'G1GC': ['-XX:+UseG1GC'],
            'CMS': ['-XX:+UseConcMarkSweepGC'],
            'Serial': ['-XX:+UseSerialGC'],
            'Parallel': ['-XX:+UseParallelGC'],
        }

        # ============ 系统属性 -D ============
        for key, value in self.system_properties.items():
            # 你的 repr 方案：先转义，再截取去掉外层引号，最后判断是否需要加双引号
            raw = str(value)
            # 判断是否需要加双引号：包含空格或特殊字符
            need_quote = any(c in raw for c in ' \t|&;()<>')
            if need_quote:
                # 用 repr 拿到转义后的字符串，去掉外层单引号，再用双引号包裹
                escaped = repr(raw)[1:-1]
                yield f'-D{key}="{escaped}"'
            else:
                yield f'-D{key}={raw}'

        # ============ 非标准选项 -X ============
        for key, value in self.non_standard_options.items():
            if isinstance(value, bool):
                if value:
                    yield f'-X{key}'
                # bool False 不输出（等同于不开启）
            else:
                yield f'-X{key}{value}'

        # ============ 高级选项 -XX ============
        for key, value in self.high_level_options.items():
            if isinstance(value, bool):
                prefix = '+' if value else '-'
                yield f'-XX:{prefix}{key}'
            else:
                yield f'-XX:{key}={value}'

        # ============ 内存配置 ============
        if self.mem_max:
            yield f'-Xmx{self.mem_max}'
        if self.mem_min:
            yield f'-Xms{self.mem_min}'
        if self.gc:
            yield from gc_flags.get(self.gc, [])

    def to_args(self) -> list[str]:
        """将 JVM 配置转换为 Java 命令行参数列表。"""
        return list(self._to_args())
