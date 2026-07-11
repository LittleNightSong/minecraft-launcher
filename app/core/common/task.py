import asyncio
import dataclasses
from collections.abc import Callable
from enum import Enum
from typing import Any, Protocol


class Tracer(Protocol):
    def trace(self, task: TaskProgress) -> Any:
        pass


class ProgressKind(Enum):
    nom = 'N/M'
    size = 'size'
    percent = 'percent'


@dataclasses.dataclass(slots=True, kw_only=True)
class TaskProgress:
    total: int | float | None = None
    progress: int | float = 0
    description: str | Any | None = None
    extra_info: Any | None = None
    progress_kind: ProgressKind = ProgressKind.percent
    visible: bool = True
    running: bool = False
    error: Any | None = None

    task: asyncio.Task | asyncio.Future | None = None

    @property
    def finished(self):
        if self.total is None: return False
        return self.total == self.progress

    def __str__(self):
        return f'<{self.__class__.__name__}: {self.description}; visible={self.visible}; running={self.running}>'

    def __iadd__(self, other):
        self.progress += other
        return self

    def __rshift__(self, other):
        self.running = bool(other)
        return self


_progress_fields = {i.name for i in dataclasses.fields(TaskProgress)}


class ReactiveProgress:
    update_callback: Callable[[TaskProgress, str, Any], Any]

    def __init__(self, progress: TaskProgress, update_callback: Callable[[TaskProgress, str, Any], Any]):
        self._p = progress
        self._u = update_callback

    def __getattr__(self, item):
        if item in _progress_fields:
            return getattr(self._p, item)
        else:
            raise AttributeError(name=item, obj=self)

    def __setattr__(self, key, value):
        if key in _progress_fields:
            setattr(self._p, key, value)
        else:
            super().__setattr__(key, value)

