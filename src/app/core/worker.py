import asyncio
from typing import Any, Protocol, Generator


class Worker[T=Any, R=None]:
    _result: R | None

    @property
    def running(self):
        return self._running

    def __init__(self):
        self.queue = asyncio.Queue()
        self._result = None
        self._result_set: bool = False
        self._sential = object()
        self._task = None
        self._running = False

    async def process_one(self, input: T):
        pass

    async def process_result(self):
        return self._result

    async def mainloop(self):
        while input := await self.queue.get():
            if input is self._sential:
                break

            await self.process_one(input)
            self.queue.task_done()

    def start(self):
        self._task = asyncio.create_task(self.mainloop())
        self._running = True

        return self

    async def stop(self, timeout=None):
        self._running = False
        await self.queue.put(self._sential)
        await asyncio.wait_for(self._task, timeout=timeout)

    async def submit(self, input: T):
        if not self._running:
            raise RuntimeError('Worker not running')

        await self.queue.put(input)

    async def result(self):
        if self._running:
            await self.stop()

        if not self._result_set:
            self._result = await self.process_result()

        return self._result


    def __await__(self):
        return self.result().__await__()


class IWorker[T, R=None](Protocol):
    @property
    def running(self) -> bool:
        ...



    async def submit(self, input: T):
        ...

    async def result(self) -> R:
        ...

    def __await__(self) -> Generator[None, None, R]:
        ...

