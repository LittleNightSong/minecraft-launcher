from datetime import datetime

from msgspec import Struct, field
from typing_extensions import Literal


class LatestStruct(Struct):
    release: str
    snapshot: str


class VersionItemStruct(Struct):
    id: str
    type: Literal['snapshot', 'release', 'old_beta', 'old_alpha']
    url: str
    time: datetime
    release_time: datetime = field(name='releaseTime')
    sha1: str
    compliance_level: int | None = field(default=None, name='complianceLevel')


class VersionManifestModel(Struct):
    latest: LatestStruct
    versions: list[VersionItemStruct]

    def find(self, id: str, type: Literal['all', 'snapshot', 'release'] = 'all'):
        for v in self.versions:
            if type != 'all' and v.type != type:
                continue

            if v.id == id:
                return v

        return None


    def build_mapping(self):
        return {v.id: v for v in self.versions}
