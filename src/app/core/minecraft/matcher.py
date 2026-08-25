import platform
import re
import typing
from typing import Literal

from app.core.models.env import Environment

type OsNameType = Literal['windows', 'linux', 'osx']
type OsArchType = Literal['x86_64', 'x86', 'arm64', 'arm']

if typing.TYPE_CHECKING:
    from app.core.models.version_meta import Rule, Rules

_os_mapping = {
    'Windows': 'windows',
    'Linux': 'linux',
    'Darwin': 'osx',
}
_arch_mapping = {
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
_system_arch = platform.machine().lower()

os_name = _os_mapping.get(platform.system(), platform.system())
os_version = platform.version()
os_arch_info = _arch_mapping.get(_system_arch, _system_arch)


def match_one(rule: Rule, env: Environment, features: dict | None = None):
    features = features or {}

    if os := rule.os:
        if (
                (name := os.get('name')) and env.os_name != name
                or (version := os.get('version')) and (re.match(version, env.os_version) is None)
                or (arch := os.get('arch')) and env.os_architecture != arch
        ):
            return False

    if required := rule.features:
        for key, value in required.items():
            if features.get(key) != value:
                return False

    return True


def match(rules: Rules, env: Environment, features: dict | None = None):
    features = features or {}
    last_result = None
    for rule in rules:
        if match_one(rule, env, features):
            last_result = rule.action

    return last_result
