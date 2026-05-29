import asyncio
import dataclasses
import time
from asyncio import TaskGroup

from loguru import logger
from niquests import HTTPError

from app.common.tasks import BaseTask
from app.network import Session


@dataclasses.dataclass(slots=True)
class DownloadTask:
    url: str
    filename: str
    session: Session
    sem: asyncio.Semaphore
    progress: int = 0
    coro: asyncio.Task = None

    async def run(self):
        with open(self.filename, 'wb') as f:
            for _ in range(10):
                try:
                    async with self.sem:
                        stream, resp = await self.session.stream_(
                            self.url,
                            chunk_size=64 * 1024,
                            headers={
                                'Range': f'bytes={self.progress}-'
                            }
                        )

                        assert resp.status_code == 206

                        async for chunk in stream:
                            f.write(chunk)
                            self.progress += len(chunk)

                    return
                except HTTPError as e:
                    if 400 <= e.response.status_code < 500:
                        raise e
                    else:
                        logger.warning(f"Error when downloading {self.url}; {e.__class__.__name__}: {e}")

                except AssertionError:
                    self.progress = 0




class MultiDownloadTask(BaseTask):
    def __init__(self, session, sem):
        self.session = session
        self.sem = sem
        self.tasks: list[DownloadTask] = []

    def add_task(self, url, filename):
        self.tasks.append(DownloadTask(url, filename, self.session, self.sem))

    async def run_wrapper(self, task):
        await task.run()
        self.progress += 1

    async def run(self, context):
        async with TaskGroup() as tg:
            for task in self.tasks:
                tg.create_task(self.run_wrapper(task))

