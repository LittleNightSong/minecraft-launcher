"""
Minecraft 版本表达式解析器。

提供了一种更灵活的版本表达方式，允许在版本号后附加名称、标记和标志。
"""

import dataclasses
import re
from dataclasses import dataclass

from app.core.common.errors import ExceptionForUser, Conflict
from app.core.i18n import tr
from .minecraft_version import MinecraftVersion

# 版本表达式正则表达式
# 格式: 版本名称@版本号,(Flags), 或者直接的 版本号
# 示例: "1.12.2@Forge:latest" "1.21.11" "

supported_loaders = {  # TODO
    # 'forge', 'neoforge',
    # 'fabric'
}

supported_shader_extensions = {  # TODO
    # 'iris', 'optifine'
}


@dataclass(slots=True)
class VersionExpr:
    """
    版本表达式解析结果。

    :ivar full_version: 解析后的 Minecraft 版本对象
    :ivar name: 版本名称（如 "我的版本"）
    :ivar flags: 附加标记列表，每个元素为 (标记名, 标记值) 元组
    """
    full_version: MinecraftVersion
    name: str | None = None
    flags: list[tuple[str, str | None]] = dataclasses.field(default_factory=list)

    def flags_to_dict(self):
        return {
            k: v for k, v in self.flags
        }

    def hybird_flags(self):
        return [
            (k, v) if v is not None else k
            for k, v in self.flags
        ]

    def validate(self):
        has_loader = False
        has_shader = False

        for f_name, f_value in self.flags:
            if f_name in supported_loaders:
                if has_loader:
                    raise ExceptionForUser(
                        Conflict(tr(
                            "模组加载器冲突, 一个实例只能拥有一种加载器"
                        ))
                    )
                else:
                    has_loader = True

            elif f_name in supported_shader_extensions:
                if has_shader:
                    raise ExceptionForUser(
                        Conflict(tr(
                            "光影拓展冲突, 一个实例只能安装一个光影拓展"
                        ))
                    )
                else:
                    has_shader = True



_mapping = {
    'r': 'rc',
    's': 'snapshot',
    'p': 'pre'
}


def parse(expr: str) -> VersionExpr | None:
    """
    解析版本表达式字符串。

    支持的格式：

    - 标准版本：1.2.3, 1.20.4
    - 预发布版：1.2r2, 1.20.4-snapshot-1
    - 带名称：我的版本:1.2r2
    - 带标记：1.2r2@forge:47,iris
    - 完整组合：我的版本:1.2r2@forge:47,iris,xxx,你好

    :param expr: 版本表达式字符串
    :return: 解析后的 VersionExpr 对象，如果解析失败则返回 None
    """
    # 首先尝试找到一个 @ ,它是版本名称和 flags 的分割
    flag_sep_index = expr.find('@')
    flags = []

    if flag_sep_index != -1:
        # 用于标记 Flags 的分隔符在 : 前面, 说明这个 expr 没有指定 version name
        # 也就是说, 在 @ 之前的东西全是 version_id
        name = expr[:flag_sep_index]
        flags_string = expr[flag_sep_index+1:]

        if flags_string:
            parts = flags_string.split(',')
            for part in parts:
                part = part.strip()
                key_sep_index = part.find(':')

                if key_sep_index != -1:
                    key = part[:key_sep_index]
                    value = part[key_sep_index+1:]

                    flags.append((key, value))
                else:
                    flags.append((part, None))

        # 尝试找到 full_version
        # 它可能位于 flags 的第一项, 无 value, 或者位于 flags 中 key 为 mc 的值, 或者就是版本名称本身
        full_version = MinecraftVersion(name)
        if flags:
            first_item = flags[0]
            if first_item[1] is None:
                full_version = MinecraftVersion(first_item[1])
            else:
                for k, v in flags:
                    if k == 'mc':
                        full_version = MinecraftVersion(v)
                        break
    else:
        name = expr.strip()
        full_version = MinecraftVersion(name)

    return VersionExpr(
        full_version=full_version,
        name=name,
        flags=flags
    )



if __name__ == '__main__':
    print(parse('我的版本@forge:47,iris,xxx,你好'))
    print(parse('我的版本@forge:47,iris,xxx,你好'))
