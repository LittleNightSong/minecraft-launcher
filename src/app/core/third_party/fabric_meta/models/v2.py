import msgspec


class LibraryStruct(msgspec.Struct, gc=False):
    name: str
    maven_url: str = msgspec.field(name='url')
    md5: str | None = None
    sha1: str | None = None
    sha256: str | None = None
    sha512: str | None = None

    size: int | None = None


class SupportedVersionListItem(msgspec.Struct, gc=False):
    version: str
    stable: bool

class LoaderListItem(msgspec.Struct, gc=False):
    separator: str
    build: int
    maven: str
    version: str
    stable: bool


class LoaderInfo(msgspec.Struct, gc=False):
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

    loader: LoaderStruct
    intermediary: IntermediaryStruct
    launcher_meta: LauncherMetaStruct = msgspec.field(name='launcherMeta')
