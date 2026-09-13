import asyncio
import builtins
from collections.abc import Buffer
from typing import Callable, Coroutine, Any

from loguru import logger

from app.core.cacher.file_cache import FileCacher
from app.core.cacher.model_cacher import ModelCacher
from app.core.common import read_model, write_model
from app.core.file_validator import FileValidator
from app.core.models import FileSpec
from app.core.network import Session
from app.core.pprofile import chronomia

type FetcherFunction[T] = Callable[[], Coroutine[Any, Any, T]]


class Fetcher:
    def __init__(
            self,
            session: Session,
            model_cacher: ModelCacher,
            file_cacher: FileCacher,
            file_validator: FileValidator | None = None
    ):
        self.session = session
        self.model_cacher = model_cacher
        self.file_cacher = file_cacher
        self.validator = file_validator
        self._task_mapping = {}

    def _assert_validator(self):
        assert self.validator is not None

    async def _fetch(self, key, type, fetcher, ttl, no_cache):
        logger.info(
            "Fetching {!r} ({!r}), fetcher={} (TTL {}), no_cache={}",
            key, type, fetcher, ttl, no_cache
        )

        if no_cache:
            logger.info("已禁用缓存，直接调用 fetcher 方法")
            return await fetcher()

        assert key

        v = self.model_cacher.get(key, type)

        if v is None:
            v = await fetcher()
            self.model_cacher.set(key, v, ttl)
            logger.info(
                "Fetched from `Fetcher` method"
            )
        else:
            logger.info(
                "Fetched from Model-Cacher"
            )
        return v

    @chronomia.async_cell
    async def fetch_model[T](
            self, *,
            fetcher: FetcherFunction[T],
            type: builtins.type[T],
            key: str | None = None,
            ttl: int | None = None,
            no_cache: bool = False
    ) -> T:
        if key not in self._task_mapping:
            self._task_mapping[key] = asyncio.create_task(
                self._fetch(key, type, fetcher, ttl, no_cache)
            )

        return await self._task_mapping[key]

    @chronomia.async_cell
    async def fetch_model_into[T](
            self, *,
            fetcher: FetcherFunction[T],
            type: builtins.type[T] | Ellipsis | None = ...,
            filename: str,
            filespec: FileSpec | None = None,
            reuse: bool = True
    ):
        self._assert_validator()

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

    @chronomia.async_cell
    async def fetch_model_into_pool[T](
            self, *,
            key: str,
            fetcher: FetcherFunction[T],
            type: builtins.type[T] | None = None,
            filespec: FileSpec | None = None,
            reuse: bool = True
    ):
        self._assert_validator()

        with self.file_cacher.open(key) as filename:
            if reuse:
                if filespec:
                    with chronomia("Validate File"):
                        v_res = await self.validator.validate(filename, filespec)
                        if v_res.ok:
                            logger.debug("文件完整性验证成功，返回数据")
                            with chronomia("Read File"):
                                return read_model(
                                    filename,
                                    type=type or ...
                                )
                        else:
                            logger.debug("文件完整性校验失败 \n{!r}", v_res)
                else:
                    try:
                        with chronomia("Read File (No Validation)"):
                            return read_model(
                                filename,
                                type=type or ...
                            )
                    except FileNotFoundError:
                        pass

            logger.debug("将从提供的 fetcher 中拉取数据")
            data = await fetcher()
            write_model(filename, data)
            return data

    @chronomia.async_cell
    async def fetch_raw_into_pool[T: bytes](
            self, *,
            key: str,
            fetcher: FetcherFunction[T],
            filespec: FileSpec | None = None,
            reuse: bool = True
    ):
        self._assert_validator()

        with self.file_cacher.open(key) as filename:
            if reuse:
                if filespec:
                    with chronomia("Validate File"):
                        v_res = await self.validator.validate(filename, filespec)
                        if v_res.ok:
                            logger.debug("文件完整性验证成功，返回数据")
                            with chronomia("Read File"):
                                return filename.read_bytes()
                        else:
                            logger.debug("文件完整性校验失败 \n{!r}", v_res)
                else:
                    try:
                        with chronomia("Read File (No Validation)"):
                            return filename.read_bytes()
                    except FileNotFoundError:
                        pass

            logger.debug("将从提供的 fetcher 中拉取数据")
            data = await fetcher()
            filename.write_bytes(data)
            return data