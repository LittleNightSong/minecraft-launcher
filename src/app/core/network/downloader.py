import asyncio
import functools
import os
from asyncio import Semaphore
from concurrent.futures import Executor
from os import PathLike
from typing import Any

import msgspec
from loguru import logger
from niquests import HTTPError

from app.core.cacher.file_cache import FileCacher
from app.core.common.errors import MaximumRetry
from app.core.network import Session
from app.core.network.session import kb256
from app.core.osio import AsyncOSFile
from app.core.task.task import TaskProgress


class HTTPDownloadPlan(msgspec.Struct, gc=False, frozen=True):
    url: str
    target: str | PathLike

    max_retry: int = 5
    headers: dict | None = None

    estimated_size: int | None = None
    is_cache: bool = False

    extra: Any | None = None


class Downloader:
    def __init__(
            self,
            max_connections: int,
            executor: Executor,
            file_cacher: FileCacher,
            session: Session | None = None,
    ):
        self.session = session or Session(pool_connections=max_connections, pool_maxsize=max_connections)
        self.semaphore = Semaphore(max_connections)
        self.executor = executor
        self.file_cacher = file_cacher

        # self.loop = asyncio.new_event_loop() # TODO 在线程从独立运行事件循环和处理下载，优先级：低
        self.loop = asyncio.get_event_loop()

    async def _download_main(
            self,
            url: str,
            filename: str | PathLike,
            progress: TaskProgress,
            headers: dict[str, str] | None = None,
    ):
        headers = headers.copy() if headers else {}

        if progress.progress != 0:  # 仅在已有进度的时候才设置 range 头
            headers['Range'] = f'bytes={progress.progress}-'  # 一般来说，这个代码总会被执行一次

        logger.info(f"针对 {url!r} 的下载：即将发送请求, headers={headers!r}")

        response = await self.session.request('GET', url, headers=headers, stream=True)

        try:
            logger.info(f"针对 {url!r} 的下载：已收到响应 {response}")

            response.raise_for_status()  # raise for status 限定了不可能下载到错误信息之类的东西

            if response.status_code == 200:  # 正常来说，这个代码总会被执行一次
                progress.total = int(response.headers.get('content-length', 0))

            await self.loop.run_in_executor(  # 异步创建父文件夹
                self.executor,
                functools.partial(os.makedirs, os.path.dirname(filename), exist_ok=True)
            )

            cnt = 0
            async with AsyncOSFile.open(
                    filename,
                    os.O_WRONLY | os.O_CREAT | os.O_BINARY,
                    buffer_size=114514 + 1919810,
                    executor=self.executor
            ) as f:
                if response.status_code != 206:  # 如果不是分片传输
                    await f.seek(0)
                    progress.progress = 0
                else:
                    await f.seek(progress.progress)

                async for chunk in await response.iter_content(kb256):
                    await f.write(chunk)
                    progress += len(chunk)

                    cnt += 1
                    if cnt % 16 == 0:
                        logger.debug(
                            "针对 {!r} 的下载（流报告）：收到的第 {} 个 chunk，当前进度：{}",
                            url, cnt, progress.progress
                        )

                logger.debug("针对 {!r} 的下载：流读取已完成，正在截断和同步磁盘写入", url)

                await f.truncate(progress.progress)  # 砍掉后面的无用数据
                await f.sync()  # 同步磁盘，确保数据落盘
        finally:
            await response.close()

    async def _download_wrapper(self, task: TaskProgress, plan: HTTPDownloadPlan):
        sleep_time = 1

        url = plan.url
        headers = plan.headers
        max_retry = plan.max_retry

        logger.debug("已创建下载任务：{}", plan)

        target = plan.target

        for i in range(max_retry + 1):
            try:
                logger.info("正在重试 （{!r}） {}/{}", url, i, max_retry)
                logger.debug(
                    "针对 {url!r} 的下载：排队中 重试次数：({i}/{max_retry})",
                    url=url, i=i, max_retry=max_retry
                )
                async with self.semaphore:
                    if plan.is_cache:
                        with self.file_cacher.open(plan.target) as file:
                            await self._download_main(url, file, task, headers)
                    else:
                        await self._download_main(url, target, task, headers)

                logger.info("针对 {!r} 的下载已完成", url)
                return

            except HTTPError as e:
                resp = e.response
                match resp.status_code:
                    case i if i in {429, 500, 502, 503, 504}:
                        retry_after = resp.headers.get('retry-after')
                        if retry_after:
                            sleep_time = int(retry_after)
                        else:
                            sleep_time *= 2
                    case _:
                        sleep_time *= 2

                logger.info("发生 HTTP 错误（错误码；{}），将在 {} 秒后自动重试", resp.status_code, sleep_time)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.opt(exception=e).warning(
                    "针对 {!r} 的下载"
                    "（进度：{}/{}，"
                    "重试：{}/{}）："
                    "未知错误 ({}) {}",
                    url, task.progress, task.total, i, max_retry, e.__class__.__name__, e
                )

        logger.error(
            "针对 {!r} 的下载：已达到最大重试次数({})，进度：{}/{}",
            url, max_retry, task.progress, task.total
        )

        raise MaximumRetry(f"无法下载 {url!r}, 已达到最大重试次数 {max_retry}")

    def create_task(self, plan: HTTPDownloadPlan):
        progress = TaskProgress()
        progress.task = asyncio.create_task(  # type: ignore
            self._download_wrapper(progress, plan)
        )
        return progress
