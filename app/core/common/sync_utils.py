import asyncio


class DynamicBarrier:
    def __init__(self):
        self._total = 0
        self._done = 0
        self._wait_event = asyncio.Event()

    async def __aenter__(self):
        self._total += 1

    async def __aexit__(self, exc_type, exc, tb):
        self._done += 1

        if self._done == self._total:
            self._wait_event.set()

        else:
            await self._wait_event.wait()