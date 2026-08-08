import asyncio
import dataclasses
from collections.abc import Callable
from enum import Enum
from types import TracebackType
from typing import Any


class ProgressKind(Enum):
    NofM = 'N of M'
    Size = 'size'
    Percent = 'percent'
    Download = 'download'


@dataclasses.dataclass(slots=True, kw_only=True)
class TaskProgress:
    total: int | float | None = None
    progress: int | float = 0
    description: str | Any | None = None
    extra_info: Any | None = None
    progress_kind: ProgressKind = ProgressKind.Percent
    visible: bool = True
    running: bool = False
    error: Any | None = None

    task: asyncio.Task | asyncio.Future | None = None

    @property
    def finished(self):
        if self.total is None: return False
        return self.total == self.progress

    def __enter__(self):
        self.running = True

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None,
                 exc_tb: TracebackType | None):
        self.running = False
        self.error = exc_val

    def __str__(self):
        return f'<{self.__class__.__name__}: {self.description}; visible={self.visible}; running={self.running}>'

    def __iadd__(self, other):
        self.progress += other
        return self

    def __rshift__(self, other):
        self.running = bool(other)
        return self

    def __await__(self):
        return self.task.__await__()


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
