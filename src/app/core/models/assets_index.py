import msgspec


class AssetsIndex(msgspec.Struct, gc=False, frozen=True, kw_only=True):
    class ObjectStruct(msgspec.Struct, frozen=True, kw_only=True, gc=False):
        path: str
        hash: str
        size: int

    objects: list[ObjectStruct]
