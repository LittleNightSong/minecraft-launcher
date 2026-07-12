import builtins
import sys

import msgspec
import niquests

from app.core.cacher.model_cacher import CacheManager

kb256 = 256 * 1024


class Session(niquests.AsyncSession):
    async def call[T](
            self, url, *args,  # 格式化 url
            method='GET', type: builtins.type[T] | None = None, headers=None,  # 请求相关的参数
    ) -> T:

        resp = await self.request(
            method,
            str(url).format(
                *map(str, args)
            ),
            headers=headers
        )
        resp.raise_for_status()

        content = resp.content

        if content is None:
            return None

        if type is None:
            return msgspec.json.decode(content)

        else:
            return msgspec.json.decode(content, type=type)

    async def call_into[T](self, url, filename, type: builtins.type[T], **kwargs) -> T:
        resp = await self.request('GET', url, **kwargs)
        resp.raise_for_status()

        content = resp.content

        if not content:
            raise ValueError("Empty content")

        with open(filename, mode='wb') as f:
            f.write(content)

        return msgspec.json.decode(content, type=type) if type else msgspec.json.decode(content)



class CachedSession(Session):
    def __init__(self, cacher: CacheManager, **kwargs):
        self.cacher = cacher
        super().__init__(**kwargs)



def make_clcl_http_session():
    return Session(
        headers={
            'user-agent': "CLCL/x.x.x ({platform})".format(platform=sys.platform),
        }
    )


session = make_clcl_http_session()
