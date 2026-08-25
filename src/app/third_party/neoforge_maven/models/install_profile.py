from typing import Literal

import msgspec
from msgspec import field

from app.third_party.mojang.models.version_meta import StandardLibraryStruct


class DataEntry(msgspec.Struct):
    client: str
    server: str


class Processor(msgspec.Struct):
    jar: str
    classpath: list[str]
    args: list[str]
    sides: list[str] = msgspec.field(default_factory=lambda :['client', 'server'])


class NeoForgeInstallProfile(msgspec.Struct):
    spec: int
    profile: str
    version: str
    icon: str
    minecraft: str
    json: str
    logo: str
    welcome: str
    mirror_list: str = field(name="mirrorList")
    hide_extract: bool = field(name="hideExtract")
    data: dict[str, DataEntry]
    processors: list[Processor]
    libraries: list[StandardLibraryStruct]
    server_jar_path: str = field(name="serverJarPath")

    def get_data(self, name, side: Literal['client', 'server']='client'):
        return getattr(self.data[name], side)

    def data_dict(self, side: Literal['client', 'server']='client'):
        return {
            k: getattr(self.data[k], side)
            for k in self.data
        }
