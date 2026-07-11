import os
import platform
import re
from pathlib import Path

from pygments.lexers import lean
from typing_extensions import Literal

type OsNameType = Literal['windows', 'linux', 'osx']
type OsArchType = Literal['x86_64', 'x86', 'arm64', 'arm']


class RulesMatcher:
    def __init__(
            self,
            os_name: OsNameType,
            os_version: str,
            os_arch: OsArchType,
            os_arch_int: Literal[32, 64]
    ):
        self.os_name: OsNameType = os_name
        self.os_version: str = os_version
        self.os_arch: OsArchType = os_arch
        self.os_arch_int: Literal[32, 64] = os_arch_int

    def match_one(self, rule, features):
        if os := rule.os:
            if (
                    (name := os.name) and self.os_name != name
                    or (version := os.version) and (re.match(version, self.os_version) is None)
                    or (arch := os.arch) and self.os_arch != arch
            ):
                return False

        if required := rule.features:
            for key, value in required.items():
                if features.get(key) != value:
                    return False

        return True

    def match(self, rules, default=True, features=None):
        features = features or {}
        last_result = None
        for rule in rules:
            if self.match_one(rule, features):
                last_result = rule.action

        return last_result == 'allow'

    def get_env(self):
        return {
            'os': self.os_name,
            'arch': self.os_arch_int,  # 这个参数只会在旧版本中被用于填充 natives 中的一些字段，只会用到它的位数
            'version': self.os_version,
        }


os_mapping = {
    'Windows': 'windows',
    'Linux': 'linux',
    'Darwin': 'osx',
}

arch_mapping = {
    'amd64': ('x86_64', 64),
    'x86_64': ('x86_64', 64),
    'x86': ('x86', 32),
    'i386': ('x86', 32),
    'i686': ('x86', 32),
    'arm64': ('arm64', 64),
    'aarch64': ('arm64', 64),
    'armv71': ('arm', 32),
    'armv61': ('arm', 32),
    '': ('x86', 32)  # 如果识别不了 machine ，那么默认当作 x86 机器
}

system_arch = platform.machine().lower()

rules_matcher = RulesMatcher(
    os_mapping.get(platform.system(), platform.system()),  # type: ignore
    platform.version(),
    *arch_mapping.get(system_arch, system_arch)  # type: ignore
)

del os_mapping, arch_mapping, system_arch


class BaseDirectory:
    path: Path

    __slots__ = ['path']

    def ensure_exists(self):
        self.path.mkdir(parents=True, exist_ok=True)

    def __fspath__(self):
        return os.fspath(self.path)

    def __truediv__(self, other) -> Path:
        return self.path / other
