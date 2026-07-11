from typing import Literal

from msgspec import Struct


class Downloads(Struct):
    sha1: str
    size: int
    url: str


class _RuleOS(Struct):
    name: str | None = None
    version: str | None = None
    arch: str | None = None


class Rule(Struct):
    action: Literal['allow', 'disallow']
    os: _RuleOS | None = None
    features: dict[str, bool] | None = None
