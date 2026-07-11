from msgspec import Struct


class _ObjectStruct(Struct):
    hash: str
    size: int


class AssetIndexModel(Struct):
    objects: dict[str, _ObjectStruct]

    def iter_object(self):
        for k, v in self.objects.items():
            yield k, v.hash, v.size
