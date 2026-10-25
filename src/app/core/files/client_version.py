"""
客户端主文件 (client jar) 内的 ``version.json`` 解析模块。

Minecraft 1.14 起, 客户端 jar 的根目录中带有 ``version.json``, 它记录了该版本的关键编号:

.. code-block:: json

    {
      "id": "1.21.1",
      "protocol_version": 767,
      "pack_version": {"resource": 34, "data": 48},
      "java_version": 21,
      "stable": true
    }

其中 ``pack_version.resource`` 是该版本支持的资源包格式, ``pack_version.data`` 是数据包格式。
"""

import zipfile
from pathlib import Path

import msgspec

# version.json 在 jar 中的位置 (不同版本偶尔会带目录前缀)
_ENTRY_NAME = 'version.json'


class PackVersion(msgspec.Struct, kw_only=True):
    """
    资源包 / 数据包的格式版本

    :ivar resource: 资源包格式 (``pack_format``)
    :ivar data: 数据包格式
    """
    resource: int | None = None
    data: int | None = None


class ClientVersionJson(msgspec.Struct, kw_only=True):
    """
    客户端 jar 中 ``version.json`` 的内容

    :ivar id: 版本号
    :ivar name: 展示名称, 通常与 ``id`` 相同
    :ivar protocol_version: 网络协议版本
    :ivar pack_version: 资源包与数据包的格式版本
    :ivar java_version: 运行时所需的 Java 主版本
    :ivar stable: 是否为稳定版本
    """
    id: str | None = None
    name: str | None = None
    protocol_version: int | None = None
    pack_version: PackVersion | None = None
    java_version: int | None = None
    stable: bool | None = None


def read_client_version_jar(jar_path: str | Path) -> ClientVersionJson | None:
    """
    从客户端 jar 中读取 ``version.json``

    以下情况都返回 ``None`` 而不是抛出异常: 文件不存在、不是合法的 zip、
    jar 中没有 ``version.json`` (1.14 之前的版本)、内容无法解析。

    :param jar_path: 客户端 jar 的路径
    :return: 解析结果, 无法获取时为 None
    """
    jar_path = Path(jar_path)

    if not jar_path.is_file():
        return None

    try:
        with zipfile.ZipFile(jar_path) as jar:
            name = next(
                (item for item in jar.namelist() if item == _ENTRY_NAME or item.endswith('/' + _ENTRY_NAME)),
                None,
            )

            if name is None:
                return None

            payload = jar.read(name)
    except (OSError, zipfile.BadZipFile, KeyError):
        return None

    try:
        return msgspec.json.decode(payload, type=ClientVersionJson)
    except (ValueError, msgspec.ValidationError):
        return None
