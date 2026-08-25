import msgspec

from app.core.models import FileSpec


class AssetsIndex(msgspec.Struct, gc=False, frozen=True, kw_only=True):
    class ObjectStruct(msgspec.Struct, frozen=True, kw_only=True, gc=False):
        vpath: str
        path: str
        hash: str
        size: int

    objects: list[ObjectStruct]

    def iter_files(self, assets_root):
        objects = assets_root / 'objects'
        for obj in self.objects:
            yield objects / obj.path, FileSpec(
                size=obj.size,
                checksum=obj.hash
            )
