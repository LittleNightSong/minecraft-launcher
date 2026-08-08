import asyncio
import dataclasses

from loguru import logger
from niquests import HTTPError

from app.core.network import Session


@dataclasses.dataclass(slots=True)
class DownloadTask:
    url: str
    filename: str
    session: Session
    limiter: asyncio.Semaphore
    progress: int = 0
    task_obj: asyncio.Task = None

    async def run(self):  # TODO: 与 router 结合，传入 method 和 args ，通过 router 获取 url 和实现负载均衡
        accept_range: bool = True

        with open(self.filename, 'wb') as f:
            for _ in range(10):
                try:
                    async with self.limiter:

                        headers = {
                            # "Accept-Encoding": "gzip, deflate, br, zstd",
                        }

                        if accept_range:
                            headers['Range'] = 'bytes={}-'.format(self.progress)

                        stream, resp = await self.session.stream_(
                            self.url,
                            chunk_size=64 * 1024,
                            headers=headers
                        )

                        if accept_range:
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
                    accept_range = False
