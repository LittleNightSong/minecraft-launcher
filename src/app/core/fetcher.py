import asyncio
import builtins
from typing import Callable, Coroutine, Any

from typer.models import AnyType

from app.core.cacher.file_cache import FileCacher
from app.core.cacher.model_cacher import ModelCacher
from app.core.common import read_model, write_model
from app.core.file_validator import FileValidator
from app.core.models import FileSpec
from app.core.network import Session

type FetcherFunction[T] = Callable[[], Coroutine[Any, Any, T]]


class Fetcher:
    def __init__(self, session: Session, model_cacher: ModelCacher, file_cacher: FileCacher,
                 file_validator: FileValidator):
        self.session = session
        self.model_cacher = model_cacher
        self.file_cacher = file_cacher
        self.validator = file_validator
        self._task_mapping = {}

    async def _fetch(self, key, type, fetcher, ttl, no_cache):
        if no_cache:
            return await fetcher()

        assert key

        v = self.model_cacher.get(key, type)
        if v is None:
            v = await fetcher()
            self.model_cacher.set(key, v, ttl)

        return v

    async def fetch_model[T](
            self, *,
            fetcher: FetcherFunction[T],
            type: type[T],
            key: str | None = None,
            ttl: int | None = None,
            no_cache: bool = False
    ) -> T:

        if key not in self._task_mapping:
            self._task_mapping[key] = asyncio.create_task(
                self._fetch(key, type, fetcher, ttl, no_cache)
            )

        return await self._task_mapping[key]

    async def fetch_model_into[T](
            self, *,
            fetcher: FetcherFunction[T],
            type: builtins.type[T] | Ellipsis | None = ...,
            filename: str,
            filespec: FileSpec | None = None,
            reuse: bool = True
    ):
        if reuse:
            if filespec:
                if (await self.validator.validate(filename, filespec)).ok:
                    return read_model(
                        filename,
                        type=type
                    )
                # else: 正常走调用 fetcher 的分支
            else:
                return read_model(
                    filename,
                    type=type
                )

        data = await fetcher()
        write_model(filename, data)
        return data

    async def fetch_model_into_pool[T](
            self, *,
            key: str,
            fetcher: FetcherFunction[T],
            type: builtins.type[T] | None = None,
            filespec: FileSpec | None = None,
            reuse: bool = True
    ):
        with self.file_cacher.open(key) as filename:
            if reuse:
                if filespec:
                    if (await self.validator.validate(filename, filespec)).ok:
                        return read_model(
                            filename,
                            type=type
                        )
                else:
                    return read_model(
                        filename,
                        type=type
                    )

            data = await fetcher()
            write_model(filename, data)
            return data
