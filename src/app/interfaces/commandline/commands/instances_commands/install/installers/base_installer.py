import dataclasses
import enum
from abc import ABC, abstractmethod
from enum import Enum
from typing import Literal, Self, AsyncIterable

import msgspec

from app.core.fetcher import Fetcher
from app.core.file_validator import FileValidator
from app.core.minecraft import Repository
from app.core.models import FileSpec, ValidateResult
from app.core.models.env import Environment
from app.core.models.version_spec import VersionSpec
from app.core.network import Session
from app.core.network.downloader import DownloadPlan


@dataclasses.dataclass(slots=True, kw_only=True)
class InstallContext:
    spec: VersionSpec
    repository: Repository
    session: Session
    fetcher: Fetcher
    file_validator: FileValidator
    env: Environment



class ValidateRequest(msgspec.Struct, gc=False, kw_only=True):
    group: str | None = None
    id: str | None = None


class LocalFileValidateRequest(ValidateRequest):
    filename: str
    spec: FileSpec


class PoolFileValidateRequest(ValidateRequest):
    filename: str
    spec: FileSpec


class ValidateResponse[T: ValidateRequest](msgspec.Struct, gc=False, kw_only=True):
    request: T
    result: ValidateResult


class ValidateResponseClassifiers(msgspec.Struct, gc=False, kw_only=True):
    groups: dict[str, list[ValidateResponse]]
    ids: dict[str, ValidateResponse]
    unnamed: list[ValidateResponse]


class Reasons(Enum):
    DISK_SPACE_INSUFFICIENT = enum.auto()
    USER_INTERRUPT = enum.auto()
    NETWORK_ERROR = enum.auto()
    BAD_VALIDATE_REQUEST = enum.auto()


class Installer(ABC):
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

    def analyze(self, result: ValidateResponseClassifiers) -> AsyncIterable[DownloadPlan]:
        ...

    async def post_install(self):
        ...

    async def on_interrupt(self, stage: Literal['fetch', 'collect', 'analyze', 'post_install'], reason: Reasons):
        ...
