import asyncio
import re


class MinecraftVersion:
    _mode_common = re.compile(r"(\d+\.\d+(\.\d+)?)(-(pre|rc)(\d+))?")
    _mode_modern = re.compile(r"(\d+\.\d+(\.\d+)?)(-(snapshot|pre|rc)-(\d+))?")
    _mode_snapshot = re.compile(r"(\d+)w(\d+)([a-z])")
    _mode_special = re.compile(r"(\d+\.\d+(\.\d+)?)( Pre-Release (\d+))")  # 1.14.2 Pre-Release 4

    __slots__ = ['version', 'major', 'minor', 'patch', 'snap', 'year', 'week', 'suffix', 'type', '__dict__']

    def __init__(self, v):
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

    def __str__(self):
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

    def __repr__(self):
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
