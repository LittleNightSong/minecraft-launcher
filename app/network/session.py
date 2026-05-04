import niquests
import orjson

kb256 = 256 * 1024


class Session(niquests.AsyncSession):
    async def call(self, url, method='GET', **kwargs):
        resp = await self.request(method, url, **kwargs)
        resp.raise_for_status()
        return orjson.loads(resp.content)

    async def download(self, url, callback, chunk_size=kb256, **kwargs):
        kwargs['stream'] = True
        resp = await self.request('GET', url, **kwargs)
        resp.raise_for_status()
        async for chunk in await resp.iter_raw(chunk_size=chunk_size):
            callback(chunk)

    async def download_async(self, url, callback, chunk_size=kb256, **kwargs):
        kwargs['stream'] = True
        resp = await self.request('GET', url, **kwargs)
        resp.raise_for_status()
        async for chunk in await resp.iter_raw(chunk_size=chunk_size):
            await callback(chunk)

    async def stream_(self, url, chunk_size=0, errorcheck=None, **kwargs):
        kwargs['stream'] = True
        resp = await self.request('GET', url, **kwargs)
        resp.raise_for_status()
        if errorcheck and not errorcheck(resp):
            raise RuntimeError()

        gen = await resp.iter_raw(chunk_size=chunk_size)
        return gen, resp


    async def call_file_based(self, url, filename, **kwargs):
        resp = await self.request('GET', url, **kwargs)
        resp.raise_for_status()
        content = resp.content
        with open(filename, mode='wb') as f:
            f.write(content)

        return orjson.loads(content)

    async def call_file_based_stream(self, url, filename, chunk_size=kb256, **kwargs):
        kwargs['stream'] = True
        resp = await self.request('GET', url, **kwargs)
        resp.raise_for_status()

        content = b''
        with open(filename, mode='wb') as f:
            async for chunk in resp.iter_async(chunk_size=chunk_size):
                content += chunk
                f.write(chunk)

        return orjson.loads(content)

session = Session()
