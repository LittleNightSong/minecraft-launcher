import dataclasses
import enum
from abc import ABC, abstractmethod
from typing import Literal, Self, AsyncIterable, Any, Iterable, ClassVar

import msgspec

from app.core.fetcher import Fetcher
from app.core.file_validator import FileValidator
from app.core.interactor import Interactor
from app.core.minecraft import Repository
from app.core.models import FileSpec, ValidateResult
from app.core.models.env import Environment
from app.core.models.version_spec import VersionSpec
from app.core.network import Session
from app.core.network.downloader import HTTPDownloadPlan


@dataclasses.dataclass(slots=True, kw_only=True)
class InstallContext:
    spec: VersionSpec
    repository: Repository
    session: Session
    fetcher: Fetcher
    file_validator: FileValidator
    env: Environment
    interactor: Interactor



class ValidateRequest(msgspec.Struct, gc=False, kw_only=True):
    group: str | None = None
    id: str | None = None

    extra: Any | None = None


class LocalFileValidateRequest(ValidateRequest):
    filename: str
    spec: FileSpec


class PoolFileValidateRequest(ValidateRequest):
    filename: str
    spec: FileSpec


class ValidateResponse[T: ValidateRequest](msgspec.Struct, gc=False, kw_only=True):
    request: T
    result: ValidateResult

    @property
    def extra(self):
        return self.request.extra

    @property
    def meta(self):
        return self.result.spec.meta

    @property
    def ok(self):
        return self.result.ok

    @property
    def spec(self):
        return self.result.spec

    # @property
    # def filename(self):
    #     return self.request.filename


class ValidateResponseSet(msgspec.Struct, gc=False, kw_only=True):
    groups: dict[str, list[ValidateResponse]]
    ids: dict[str, ValidateResponse]
    lost: list[ValidateResponse]

    def get_responses(self, group=None, ids: Iterable[str] | None = None):
        if group:
            yield from self.groups.get(group, [])
        if ids:
            for id in ids:
                yield self.ids[id]



class Reasons(enum.Enum):
    DISK_SPACE_INSUFFICIENT = enum.auto()
    USER_INTERRUPT = enum.auto()
    NETWORK_ERROR = enum.auto()
    BAD_VALIDATE_REQUEST = enum.auto()


class Installer(ABC):
    prefix: ClassVar[str] = 'Unknown'

    @classmethod
    @abstractmethod
    async def get_installer(cls, context: InstallContext) -> Self | None:
        ...

    async def init(self):
        ...

    async def fetch(self):
        ...

    def collect(self) -> AsyncIterable[ValidateRequest]:
        ...

    def pre_download(self, result: ValidateResponseSet) -> AsyncIterable[HTTPDownloadPlan]:
        ...

    async def post_download(self, download_plans: list[HTTPDownloadPlan]):
        ...

    async def post_install(self):
        ...

    async def on_interrupt(self, stage: Literal['fetch', 'collect', 'analyze', 'post_install'], reason: Reasons):
        ...
