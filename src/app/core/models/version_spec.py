from typing import Literal

import msgspec


class VersionSpec(msgspec.Struct, gc=False, kw_only=True):
    name: str | None
    version: str

    loader: Literal['forge', 'neoforge', 'fabric'] | None = None
    loader_version: str | None = None
