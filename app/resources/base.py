import os
import platform
import re
from pathlib import Path


class RulesMatcher:
    def __init__(self, os_name, os_version, os_arch):
        self.os_name = os_name
        self.os_version = os_version
        self.os_arch = os_arch

    def match_one(self, rule, **features):
        if os := rule.get('os'):
            if (
                    (name := os.get('name')) and self.os_name != name
                    or (version := os.get('version')) and (re.match(version, self.os_version) is None)
                    or (arch := os.get('arch')) and self.os_arch != arch
            ):
                return False

        if required := rule.get('features'):
            for key, value in required.items():
                if features.get(key) != value:
                    return False

        return True

    def match(self, rules):
        last_result = False
        for rule in rules:
            if self.match_one(rule):
                last_result = rule['action'] == 'allow'
            else:
                return last_result

        return None


os_mapping = {
    'Windows': 'windows',
    'Linux': 'linux',
    'Darwin': 'osx',
}

arch_mapping = {
    'amd64': 'x86_64',
    'x86_64': 'x86_64',
    'x86': 'x86',
    'i386': 'x86',
    'i686': 'x86',
    'arm64': 'arm64',
    'aarch64': 'arm64',
    'armv71': 'arm',
    'armv61': 'arm',
}

system_arch = platform.machine().lower()

rules_matcher = RulesMatcher(
    os_mapping.get(platform.system(), platform.system()),
    platform.version(),
    arch_mapping.get(system_arch, system_arch)
)

del os_mapping, arch_mapping, system_arch


class BaseDirectory:
    path: Path

    __slots__ = ['path']

    def ensure_exists(self):
        self.path.mkdir(parents=True, exist_ok=True)

    def __fspath__(self):
        return os.fspath(self.path)

    def __divmod__(self, other) -> Path:
        return self.path / other
