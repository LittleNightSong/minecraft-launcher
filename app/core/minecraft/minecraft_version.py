"""
Minecraft 版本解析器模块。

提供 Minecraft 版本号的解析和结构化表示功能。
支持正式版、快照版、预发布版、远古版本等多种版本格式。
"""

import asyncio
import re


class MinecraftVersion:
    """
    Minecraft 版本解析器。

    解析 Minecraft 版本号字符串，提取版本类型、主次版本号、补丁号等结构化信息。

    支持以下版本格式：
    - 正式版：1.20.4, 1.21
    - 快照版（现代）：23w16a, 1.21-snapshot-1
    - 预发布版：1.20.4-pre1, 1.21-rc2
    - 传统快照：1.2r2, 1.3s1
    - 远古版本：a1.0.0, b1.7.3, c0.0.1, inf-20100618
    - 愚人节版本：1.17.22, 1.14.2 Pre-Release 4

    :ivar version: 原始版本字符串
    :ivar major: 主版本号（如 1）
    :ivar minor: 次版本号（如 20）
    :ivar patch: 补丁号（如 4），不存在时为 0
    :ivar snap: 快照/预发布编号（如 1），不存在时为 0
    :ivar year: 快照年份（仅传统快照格式）
    :ivar week: 快照周数（仅传统快照格式）
    :ivar suffix: 快照后缀字母（仅传统快照格式）
    :ivar type: 版本类型，可选 'release'、'snapshot'、'pre'、'rc'、'snapshot(legacy)'、'april fool'、'old'
    """
    _mode_common = re.compile(r"(\d+\.\d+(\.\d+)?)(-(pre|rc)(\d+))?")
    _mode_modern = re.compile(r"(\d+\.\d+(\.\d+)?)(-(snapshot|pre|rc)-(\d+))?")
    _mode_snapshot = re.compile(r"(\d+)w(\d+)([a-z])")
    _mode_special = re.compile(r"(\d+\.\d+(\.\d+)?)( Pre-Release (\d+))")  # 1.14.2 Pre-Release 4

    __slots__ = ['version', 'major', 'minor', 'patch', 'snap', 'year', 'week', 'suffix', 'type', '__dict__']

    def __init__(self, v: str):
        """
        初始化版本解析器。

        :param v: 版本号字符串
        """
        v = str(v).strip()

        # 先进行特殊版本匹配
        if v.startswith(('a', 'b', 'c', 'inf', 'rd')):
            self.type = 'old'
            return

        self.version = v

        self.major = None
        self.minor = None
        self.patch = None

        self.snap = None

        self.year = None
        self.week = None
        self.suffix = None

        self.type = None

        if res := self._mode_common.fullmatch(v):
            self.type = res[4] or 'release'
            split = res[1].split('.')
            self.major, self.minor = map(int, split[:2])
            self.patch = int(split[2]) if len(split) > 2 else 0
            self.snap = int(res[5] or 0)
        elif res := self._mode_modern.fullmatch(v):
            self.type = res[4] or 'release'
            split = res[1].split('.')
            self.major, self.minor = map(int, split[:2])
            self.patch = int(split[2]) if len(split) > 2 else 0
            self.snap = int(res[5] or 0)

            if self.major == 1 and self.type != 'release':
                # modern 格式的版本号仅适用于 26.1 以后的版本，之前的版本，比如 1.21.11 不应该使用
                # 这个操作只会影响 pre 和 rc 类型的版本
                self.version = (  # 重新组装版本号
                        f'{self.major}.{self.minor}' +
                        (f'.{self.patch}' if self.patch else '') + f'-{self.type}{self.snap}'
                )

        elif res := self._mode_snapshot.fullmatch(v):
            self.type = 'snapshot(legacy)'
            groups = res.groups()
            self.year, self.week = map(int, groups[0:2])
            self.suffix = res[3]
        elif res := self._mode_special.fullmatch(v):
            self.type = 'pre'
            groups = res.groups()
            split = groups[0].split('.')
            self.major, self.minor = map(int, split[:2])
            self.minor = int(split[2]) if len(split) > 2 else 0
            self.snap = int(groups[3] or 0)
        else:
            self.type = 'april fool'

    def __str__(self) -> str:
        """
        返回版本对象的详细字符串表示。

        :return: 包含版本类型和详细信息的字符串
        """
        match self.type:
            case 'snapshot':
                return (f'{self.__class__.__name__}<{self.version}>'
                        f'(Snapshot; major={self.major}, minor={self.minor}, patch={self.patch}, '
                        f'snap={self.snap})')
            case 'snapshot(legacy)':
                return (f'{self.__class__.__name__}<{self.version}>(Snapshot(legacy); '
                        f'year={self.year}, week={self.week}, suffix={self.suffix!r})')
            case 'april fool':
                return f'{self.__class__.__name__}<{self.version}>(April Fool; {self.version})'
            case 'release':
                return f'{self.__class__.__name__}<{self.version}>(Release; major={self.major}, minor={self.minor}, patch={self.patch})'
            case x if x in {'pre', 'rc'}:
                return (f'{self.__class__.__name__}<{self.version}>'
                        f'({self.type.title()}; major={self.major}, minor={self.minor}, patch={self.patch}, '
                        f'snap={self.snap})')
            case type:
                raise ValueError(f"Undefined type {type}")

    def __repr__(self) -> str:
        """
        返回版本对象的简洁字符串表示。

        :return: 可重现对象的字符串表示
        """
        return f'{self.__class__.__name__}({self.version})'


if __name__ == '__main__':
    from app.interfaces.command.methods import shell_get_version_manifest
    from app.core.network.session import session

    async def main():
        async with session:
            manifest = await shell_get_version_manifest()
            for version in manifest['versions']:
                print(f"{version['id']:20} ", end='')
                print(MinecraftVersion(version['id']))

    asyncio.run(main())