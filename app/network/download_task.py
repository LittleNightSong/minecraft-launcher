import time

from loguru import logger
from niquests import HTTPError

from app.common.tasks import BaseTask
from app.network import Session


class DownloadTask(BaseTask):
    def __init__(self, url, filename, session: Session):
        super().__init__()
        self.url = url
        self.filename = filename
        self.session = session

        self.visible = False

    async def run(self):
        self.status = '[dim]Open File[/dim]'
        with open(self.filename, 'wb') as f:
            for _ in range(10):
                try:
                    self.status = '[dim]Watting for response[/dim]'
                    stream, resp = await self.session.stream_(
                        self.url,
                        chunk_size=1024*1024,
                        headers={
                            'Range': f'bytes=0-{self.progress}'
                        }
                    )
                    start_time = time.time()

                    assert resp.status_code == 206

                    async for chunk in stream:
                        f.write(chunk)
                        self.progress += len(chunk)

                        time_remaining = self.total / self.progress * (time.time() - start_time)
                        if not self.visible and time_remaining > 10:
                            self.visible = True

                    self.status = '[green]Ok[/green]'
                    return
                except HTTPError as e:
                    if 400 <= e.response.status_code < 500:
                        raise e
                    else:
                        logger.warning(f"Error when downloading {self.url}; {e.__class__.__name__}: {e}")

                except AssertionError:
                    pass