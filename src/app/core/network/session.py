import builtins
import urllib.parse

import msgspec
import niquests

kb256 = 256 * 1024


class Session(niquests.AsyncSession):
    async def typed[T](
            self, url, *args,  # 格式化 url
            method='GET',
            type: builtins.type[T] | None = None,
            data: bytes | None = None,
            headers=None,  # 请求相关的参数
    ) -> T:

        content = await self.read(
            str(url).format(
                [urllib.parse.quote(str(x)) for x in args]
            ),
            method,
            data=data,
            headers=headers
        )

        if content is None:
            return None

        return (
            msgspec.json.decode(content)
            if type is None
            else
            msgspec.json.decode(content, type=type)
        )

    async def typed_download[T](self, url, filename, type: builtins.type[T], allow_empty=False, **kwargs) -> T:
        content = await self.read(url)

        if not content:
            if not allow_empty:
                raise ValueError("Empty content")
            else:
                with open(filename, 'wb') as f:
                    pass
                return None

        with open(filename, mode='wb') as f:
            f.write(content or b'')

        return msgspec.json.decode(content, type=type) if type else msgspec.json.decode(content)

    async def read(self, url, method='GET', headers=None, data: bytes | None = None) -> bytes | None:
        resp = await self.request(
            method,
            url,
            data=data, headers=headers
        )
        resp.raise_for_status()
        c = resp.content
        resp.close()
        return c

    async def text(self, url, method='GET', headers=None, data: bytes | None = None,
                   encoding: str = 'utf-8') -> str | None:
        resp = await self.request(
            method,
            url,
            data=data, headers=headers
        )
        resp.raise_for_status()
        c = resp.content
        resp.close()
        return c.decode(encoding) if c else None
