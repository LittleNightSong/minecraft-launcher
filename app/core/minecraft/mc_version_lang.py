import dataclasses
import re
from dataclasses import dataclass

from app.core.minecraft import MinecraftVersion

_matcher = re.compile(
    r"([_\w.-]+=)?"  # 版本名称
    r"(\d+\.\d+(\.\d+)?)"  # 主版本号
    r"([srp]\d+)?"  # 可能的 snapshot/rc/pre 标记
    r"(@(\w+(:\w+)?)(,(\w+(:\w+)?))*)?"  # 附加标记
    r"(=\w+)?"  # 版本名称    
    r"$"
)


@dataclass(slots=True)
class VersionExpr:
    full_version: MinecraftVersion
    name: str | None = None
    flags: list[tuple[str, str]] = dataclasses.field(default_factory=list)


_mapping = {
    'r': 'rc',
    's': 'snapshot',
    'p': 'pre'
}


def parse(expr: str):
    if match := _matcher.match(expr):
        groups = match.groups()

        version = groups[1]
        if type_ := groups[3]:
            version += f'-{_mapping[type_[0]]}-{type_[1:]}'

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
    print(_matcher.match('我的版本=1.2r2@forge:47,iris,xxx,你好').groups())
    print(parse('我的版本=1.2r2@forge:47,iris,xxx,你好'))
    print(parse('我的版本=1.2.114514p2@forge:47,iris,xxx,你好'))
