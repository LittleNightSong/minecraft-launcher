from typing import AsyncGenerator

import niquests
import orjson
from niquests import Response

kb256 = 256 * 1024


class Session(niquests.AsyncSession):
    def __init__(self):
        super().__init__(multiplexed=True)

    async def call(self, url, method='GET', **kwargs):
        kwargs.pop('stream', False)
        resp = await self.request(method, url, **kwargs)
        await self.gather(resp)
        resp.raise_for_status()
        return orjson.loads(resp.content)

    async def download(self, url, callback, chunk_size=kb256, **kwargs):
        kwargs['stream'] = True
        stream, resp = await self.stream_(url, chunk_size, **kwargs)
        for chunk in resp.iter_content(chunk_size=chunk_size):
            callback(chunk)

    async def download_async(self, url, callback, chunk_size=kb256, **kwargs):
        kwargs['stream'] = True
        stream, resp = await self.stream_(url, chunk_size, **kwargs)
        async for chunk in stream:
            await callback(chunk)

    async def stream_(self, url, chunk_size=0, errorcheck=None, **kwargs) -> tuple[AsyncGenerator[bytes, None], Response]:
        kwargs['stream'] = True
        resp = await self.request('GET', url, **kwargs)
        await self.gather(resp)
        resp.raise_for_status()
        if errorcheck and not errorcheck(resp):
            raise RuntimeError()

        gen = await resp.iter_content(chunk_size=chunk_size)
        if gen is None:
            raise RuntimeError()
        return gen, resp


    async def call_file_based(self, url, filename, **kwargs):
        resp = await self.request('GET', url, **kwargs)
        await self.gather(resp)
        resp.raise_for_status()

        content = resp.content
        with open(filename, mode='wb') as f:
            f.write(content)

        return orjson.loads(content)

    async def call_file_based_stream(self, url, filename, chunk_size=kb256, **kwargs):
        stream, resp = await self.stream_(url, chunk_size, **kwargs)

        content = b''
        with open(filename, mode='wb') as f:
            async for chunk in stream:
                content += chunk
                f.write(chunk)

        return orjson.loads(content)

session = Session()
