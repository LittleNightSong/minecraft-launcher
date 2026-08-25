from datetime import datetime

import msgspec

import app.core.models.version_meta
from app.core.models import Library
from app.third_party.mojang.models.version_meta import ArgumentsStruct


class LibraryStruct(msgspec.Struct, gc=False):
    name: str
    maven_url: str = msgspec.field(name='url')
    md5: str | None = None
    sha1: str | None = None
    sha256: str | None = None
    sha512: str | None = None

    size: int | None = None

    def unify(self) -> app.core.models.version_meta.CommonLibraryStruct:
        L = app.core.models.version_meta.LibraryStruct
        C = app.core.models.version_meta.CommonLibraryStruct

        artifact = L(self.name, str(Library(self.name).path), sha1=self.sha1, size=self.size, maven_url=self.maven_url)
        return C(artifact=artifact)


class LauncherMetaStruct(msgspec.Struct, gc=False):
    class LibrariesStruct(msgspec.Struct, gc=False):
        client: list[LibraryStruct]
        server: list[LibraryStruct]
        common: list[LibraryStruct]
        development: list[LibraryStruct]

    class MainClassStruct(msgspec.Struct, gc=False):
        client: str
        server: str

    version: int
    min_java_version: int

    libraries: LibrariesStruct
    mainclass: MainClassStruct = msgspec.field(name='mainClass')


class SupportedVersionListItem(msgspec.Struct, gc=False):
    version: str
    stable: bool


class LoaderStruct(msgspec.Struct, gc=False):
    separator: str
    build: int
    maven: str
    version: str
    stable: bool


class IntermediaryStruct(msgspec.Struct, gc=False):
    maven: str
    version: str
    stable: bool

    def is_deprecated(self) -> bool:
        return self.version == '0.0.0'


class LoaderDetailListItem(msgspec.Struct, gc=False):
    loader: LoaderStruct
    intermediary: IntermediaryStruct
    # launcher_meta: LauncherMetaStruct


class LoaderInfo(msgspec.Struct, gc=False):
    loader: LoaderStruct
    intermediary: IntermediaryStruct
    launcher_meta: LauncherMetaStruct = msgspec.field(name='launcherMeta')


class LoaderProfile(msgspec.Struct, gc=False):
    id: str
    inherits_from: str = msgspec.field(name='inheritsFrom')
    release_time: datetime = msgspec.field(name='releaseTime')
    time: datetime
    type: str
    main_class: str = msgspec.field(name='mainClass')
    arguments: ArgumentsStruct
    libraries: list[LibraryStruct] = []
