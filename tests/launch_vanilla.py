from pathlib import Path

import orjson

minecraft = Path('./.minecraft')
version = '1.19.2'


class ProcessBuilder:
    def __init__(self, executable, *args):
        self.executable = executable
        self.args = list(args)

    def add_argument(self, arg):
        self.args.append(arg)

    def add_arguments(self, *args):
        for arg in args:
            self.add_argument(arg)

    def __iadd__(self, other):
        if isinstance(other, list):
            self.args.extend(other)
        else:
            self.args.append(other)




async def main():
    instance_dir = minecraft / version
    # 1. 读取自述文件
    desc = orjson.loads((instance_dir / f'{version}.json').read_bytes())
    proc = ProcessBuilder('java.exe')

    main_class = desc['mainClass']
    # 准备 logging 配置文件

