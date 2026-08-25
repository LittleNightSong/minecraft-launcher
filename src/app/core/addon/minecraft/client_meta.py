from datetime import datetime

import msgspec


class ClientMeta(msgspec.Struct, kw_only=True, gc=False):
    id: str
    name: str
    world_version: int
    series_id: str
    protocol_version: int

    pack_version: PackVersionStruct

    class PackVersionStruct(msgspec.Struct):
        # type 1
        resource: int | None = None
        data: int | None = None

        # type 2 (Newer)

        resource_major: int | None = None
        resource_minor: int | None = None

        data_major: int | None = None
        data_minor: int | None = None

        def __post_init__(self):
            old_ones = (self.resource, self.data)
            new_ones = (self.resource_major, self.resource_minor, self.data_major, self.data_minor)

            if not (all(old_ones) or all(new_ones)):
                raise msgspec.ValidationError("不完整的结构")

        @property
        def resource_version(self):
            if self.resource:
                return self.resource
            else:
                return self.resource_major, self.resource_minor

        @property
        def data_version(self):
            if self.data:
                return self.data
            else:
                return self.data_major, self.data_minor

    build_time: datetime
    java_component: str
    java_version: int
    stable: bool
    use_editor: bool
