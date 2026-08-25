from typing import AsyncGenerator

from rtzip import RemoteZip as _RemoteZip
from rtzip.remotezip import DataSourceCallbacks

from app.core.network import Session


class URLSource(DataSourceCallbacks):
    def __init__(self, url: str, session: Session):
        self.session = session
        self.url = url

    async def get_total_size(self) -> int:
        resp = await self.session.head(self.url)
        resp.raise_for_status()

        return int(resp.headers["Content-Length"])

    async def read_range(self, offset, length) -> bytes | bytearray | memoryview:
        resp = await self.session.get(self.url, headers={
            'Range': f'bytes={offset}-{offset+length-1}'
        }, stream=True)
        resp.raise_for_status()
        if resp.status_code == 206:
            data = await resp.content
            assert data and len(data) == length
            await resp.close()
            return data
        else:
            await resp.close()
            raise RuntimeError()

    async def read_range_stream(self, offset, length) -> AsyncGenerator[bytes | bytearray | memoryview]:
        resp = await self.session.get(
            self.url,
            headers={
                'Range': f'bytes={offset}-{offset+length-1}'
            },
            stream=True, timeout=10
        )
        resp.raise_for_status()
        if resp.status_code == 206:
            async for i in await resp.iter_content():
                yield i
            await resp.close()
        else:
            await resp.close()
            raise RuntimeError()


class RemoteZip(_RemoteZip):
    def __init__(self, url: str, session: Session):
        super().__init__(URLSource(url, session))