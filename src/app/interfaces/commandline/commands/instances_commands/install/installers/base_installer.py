import enum
from abc import ABC, abstractmethod
from enum import Enum
from typing import Literal, Self, AsyncIterable

import msgspec

from app.core.fetcher import Fetcher
from app.core.models import FileSpec, ValidateResult
from app.core.models.env import Environment
from app.core.models.version_spec import VersionSpec
from app.core.network import Session
from app.core.network.downloader import DownloadPlan


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
    uncategorized: list[ValidateResponse]
    categories: dict[str, list[ValidateResponse]]

    def get_responses(self, category: str):
        return self.categories.get(category, [])

    def assert_category(self, category: str):
        assert category in self.categories


class Reasons(Enum):
    DISK_SPACE_INSUFFICIENT = enum.auto()
    USER_INTERRUPT = enum.auto()


class Installer(ABC):
    @classmethod
    @abstractmethod
    async def get_installer(cls, spec: VersionSpec, session: Session, fetcher: Fetcher,
                            env: Environment) -> Self | None:
        ...

    async def init(self):
        ...

    async def fetch(self):
        ...

    def collect(self) -> AsyncIterable[ValidateRequest]:
        ...

    def analyze(self, result: list[ValidateResult]) -> AsyncIterable[DownloadPlan]:
        ...

    async def post_install(self):
        ...

    async def on_interrupt(self, stage: Literal['fetch', 'collect', 'analyze', 'post_install'], reason: Reasons):
        ...
