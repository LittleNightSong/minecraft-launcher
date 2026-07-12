"""
Minecraft 版本表达式解析器。

提供了一种更灵活的版本表达方式，允许在版本号后附加名称、标记和标志。
"""

import dataclasses
import re
from dataclasses import dataclass

from app.core.common.errors import ExceptionForUser, Conflict
from app.core.i18n import tr
from app.core.minecraft import MinecraftVersion

# 版本表达式正则表达式
# 格式: [名称=]主版本号[后缀] [@标记1,标记2,...] [=版本名称]
# 示例: "我的版本:1.2r2@forge:47,iris,xxx,你好"
_matcher = re.compile(
    r"(([_\w.-]+):)?"  # 版本名称前缀
    r"([a-zA-Z0-9.-]+)"  # 主版本名
    r"(@(\w+(:\w+)?)(,(\w+(:\w+)?))*)?"  # 附加标记
    r"(=\w+)?"  # 版本名称后缀
    r"$"
)

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
    flags: list[tuple[str, str]] = dataclasses.field(default_factory=list)

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

    def export_without_name(self):
        part_version = ''


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
    if match := _matcher.match(expr):
        groups = match.groups()

        version = groups[2]
        full_version = MinecraftVersion(version)

        if name := groups[0]:
            name = name[:-1]

        flags = []
        if flags_string := groups[4]:
            flags_string = flags_string[1:]
            for flag_expr in flags_string.split(','):
                split = flag_expr.split(':')
                if len(split) == 2:
                    flags.append(tuple(split))
                else:
                    flags.append((split[0], None))

        return VersionExpr(
            full_version,
            name,
            flags
        )

    else:
        return None


if __name__ == '__main__':
    print(_matcher.match('我的版本:26.2-rc-2@forge:47,iris,xxx,你好').groups())
    print(parse('我的版本:1.2r2@forge:47,iris,xxx,你好'))
    print(parse('我的版本:1.2.114514p2@forge:47,iris,xxx,你好'))
