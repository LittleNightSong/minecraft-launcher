import asyncio
import dataclasses
from asyncio import TaskGroup
from enum import Enum
from typing import Any


class ProgressKind(Enum):
    nom = 'N of M'
    size = 'size'
    percent = 'percent'


@dataclasses.dataclass(slots=True)
class Context:
    input: Any
    output: Any = None

    vars: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __getattr__(self, item):
        try:
            return self.vars[item]
        except KeyError as e:
            raise AttributeError(e)


class BaseTask:
    coro: asyncio.Task

    total: int | float | None = None
    progress: int | float = 0
    description: str | Any | None = None
    extra_info: Any | None = None
    progress_kind: ProgressKind = ProgressKind.percent
    visible: bool = True

    async def run(self, context: Context):
        ...


class SequenceTask(BaseTask):
    def __init__(self, tasks: list[BaseTask]):
        self.tasks = tasks
        self.progress = 0

    @property
    def current_task(self):
        return self.tasks[self.progress]

    @property
    def total(self):
        return len(self.tasks)

    async def run(self, context):
        input = context.input
        for task in self.tasks:
            await task.run(cur := Context(input=input))
            input = cur.output
            self.progress += 1


class ParallelTask(BaseTask):
    def __init__(self, tasks: list[BaseTask]):
        self.tasks = tasks
        self.progress = 0

    @property
    def total(self):
        return len(self.tasks)

    async def run_wrapper(self, task, context: Context):
        await task.run(context)
        self.progress += 1

    async def run(self, context):
        async with TaskGroup() as tg:
            for task in self.tasks:
                tg.create_task(self.run_wrapper(task, Context(input=context.input)))
