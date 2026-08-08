# env.py
# Doc by DeepSeek
import dataclasses
import platform
import typing
from typing import Literal


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

os_name: Literal['windows', 'linux', 'osx'] = _os_mapping.get(platform.system(), 'windows')
os_version = platform.version()
os_arch_info = _arch_mapping.get(_system_arch, _system_arch)


@dataclasses.dataclass(frozen=True, slots=True)
class Environment:
    """
    操作系统环境信息类。

    表示当前运行环境的操作系统信息，包括系统名称、版本、架构等。

    :ivar os_name: 操作系统的名称（类型），可选 'windows'、'linux'、'macos'
    :ivar os_version: 操作系统的版本号
    :ivar os_architecture: 操作系统的架构（完整字符串），如 'AMD64'、'aarch64'
    :ivar os_arch: 操作系统的位数，32 或 64
    """
    os_name: Literal['windows', 'linux', 'osx']
    os_version: str
    os_architecture: str
    os_arch: int

    def to_dict(self):
        """
        将环境信息转换为字典格式。

        :return: 包含环境信息的字典，键为 'name'、'version'、'architecture'、'arch'
        """
        return {
            'name': self.os_name,
            'version': self.os_version,
            'architecture': self.os_architecture,
            'arch': self.os_arch
        }

    @typing.overload
    def replace(self, *, name: str = ..., version: str = ..., architecture: str = ..., arch: int = ...):
        """
        替换环境信息的字段（类型重载）。

        :param name: 新的操作系统名称
        :param version: 新的操作系统版本号
        :param architecture: 新的操作系统架构字符串
        :param arch: 新的操作系统位数
        """
        ...

    @typing.overload
    def replace(self, **kwargs):
        """
        替换环境信息的字段（通用重载）。

        :param kwargs: 任意字段名和对应的新值
        """
        ...

    def replace(self, **kwargs):
        """
        创建一个新的 Environment 实例，替换指定的字段。

        :param kwargs: 要替换的字段名和对应的新值
        :return: 新的 Environment 实例
        """
        return dataclasses.replace(self, **kwargs)

    def __getitem__(self, item):
        return self.to_dict()[item]

    @classmethod
    def new(cls):
        return Environment(
            os_name,
            os_version,
            *os_arch_info
        )
