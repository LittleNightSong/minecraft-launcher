"""
Minecraft 版本解析器模块。

提供 Minecraft 版本号的解析和结构化表示功能。
支持正式版、快照版、预发布版、远古版本等多种版本格式。
"""

import re

inf = float('inf')


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

    # 额外的版本格式, 由 from_string() 在常规构造之后修正
    # 1.RV-Pre1: 第二个"版本号"其实是字母代号, 因此不能写成 \d+
    _mode_dotted_pre = re.compile(r"(\d+)\.([A-Za-z][A-Za-z0-9_]*)-(?:[A-Za-z]+)?(\d+)")
    _mode_modern_part = re.compile(r"(\d+\.\d+(?:\.\d+)?)-(?:snapshot|pre|rc)-(\d+)")  # 26.4-snapshot-2

    # 已经被 from_string() 修正过的版本号, 避免重复修正 (每次 from_string 都是新对象)
    _patched: set[str] = set()

    _type_mapping = {
        'old': 0,
        'snapshot': 1,
        'snapshot(legacy)': 1,
        'rc': 2,
        'pre': 3,
        'release': 4,
    }

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
            self.version = v
            return

        self.version = v

        self.major = None
        self.minor = None
        self.patch = None

        self.snap = None

        self.year = None
        self.week = None
        self.suffix = None

        self.type: str

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

    @property
    def main_type(self):
        return self.type.removesuffix('(legacy)')

    @classmethod
    def from_string(cls, v: str) -> "MinecraftVersion":
        """
        由版本号字符串创建版本对象, 并修正若干容易被误判的格式

        与直接构造 ``MinecraftVersion(...)`` 不同, 这里会额外处理两种特殊写法:

        - ``1.RV-Pre1`` 这类愚人节版本会被识别为预览版;
        - ``26.4-snapshot-2`` 让 minor 保持为 4, 而不是像常规解析那样把补丁号当作 minor。

        :param v: 版本号字符串
        :return: 版本对象
        """
        version = cls(v)

        if version.version in cls._patched:
            return version

        if res := cls._mode_dotted_pre.fullmatch(version.version):
            # 1.RV-Pre1 -> 主版本 1, 次版本 0 (RV 是代号), 预览编号 1
            version.type = 'pre'
            version.major = int(res[1])
            version.minor = 0
            version.patch = 0
            version.snap = int(res[3])
            cls._patched.add(version.version)

        elif res := cls._mode_modern_part.fullmatch(version.version):
            # 26.4-snapshot-2 会被 _mode_common 吃掉, 但它其实是 26.4 的快照:
            # 需要让 minor 保持为 4, 而不是把快照编号当成 minor
            parts = res[1].split('.')
            version.major, version.minor = map(int, parts[:2])
            version.patch = int(parts[2]) if len(parts) > 2 else 0
            version.snap = int(res[2])
            cls._patched.add(version.version)

        return version

    def __str__(self) -> str:
        """
        返回版本对象的详细字符串表示。

        :return: 包含版本类型和详细信息的字符串
        """
        match self.type:
            case 'snapshot':
                return (f'{self.__class__.__name__}<snapshot | {self.version!r}>'
                        f'(Snapshot; major={self.major}, minor={self.minor}, patch={self.patch}, '
                        f'snap={self.snap})')
            case 'snapshot(legacy)':
                return (f'{self.__class__.__name__}<legacy-snapshot | {self.version!r}>(Snapshot(legacy); '
                        f'year={self.year}, week={self.week}, suffix={self.suffix!r})')
            case 'april fool':
                return f'{self.__class__.__name__}<af | {self.version!r}>(April Fool; {self.version!r})'
            case 'release':
                return f'{self.__class__.__name__}<common | {self.version!r}>(Release; major={self.major}, minor={self.minor}, patch={self.patch})'
            case x if x in {'pre', 'rc'}:
                return (f'{self.__class__.__name__}<{x} | {self.version!r}>'
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

    # noinspection method-overriding
    def __eq__(self, other):
        return self.version == other.version

    def __gt__(self, other):
        assert isinstance(other, self.__class__)

        if self.type in {'old', 'april fool'}:
            return False

        elif other.type in {'old', 'april fool'}:
            return True

        match self.type:
            case x if x in {'release', 'snapshot', 'pre', 'src'}:
                if other.type in {'release', 'snapshot', 'pre', 'rc'}:
                    return (
                        self.major, self.minor, self.patch, self.snap or float('inf')
                    ) > (
                        other.major, other.minor, other.patch, other.snap or float('inf')
                    )
                else:
                    return False
            case 'snapshot(legacy)':
                if other.type == 'snapshot(legacy)':
                    return (self.year, self.week, self.suffix) > (other.year, other.week, other.suffix)
                else:
                    return False

    def __lt__(self, other):
        assert isinstance(other, self.__class__)

        if self.type in {'old', 'april fool'}:
            return True

        if other.type in {'old', 'april fool'}:
            return False

        match self.type:
            case x if x in {'release', 'snapshot', 'pre', 'src'}:
                if other.type in {'release', 'snapshot', 'pre', 'rc'}:
                    return (
                        self.major, self.minor, self.patch, self._type_mapping[self.type], self.snap or inf
                    ) < (
                        other.major, other.minor, other.patch, self._type_mapping[other.type], other.snap or inf
                    )
                else:
                    return False
            case 'snapshot(legacy)':
                if other.type == 'snapshot(legacy)':
                    return (self.year, self.week, self.suffix) < (other.year, other.week, other.suffix)
                else:
                    return False

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def __hash__(self):
        return hash(self.version)


if __name__ == '__main__':
    v = MinecraftVersion('26w14a')
    v2 = MinecraftVersion('26w14b')
    print(v)
    print(v2)
    print(v2 < v)
