import asyncio
import functools
import os
import shutil
import time
from asyncio import Semaphore
from concurrent.futures import Executor
from os import PathLike
from typing import Iterable, Literal

import msgspec
from loguru import logger
from niquests import HTTPError

from app.core.cacher.file_cache import FileCacher
from app.core.common.errors import MaximumRetry
from app.core.task.task import TaskProgress
from app.core.network import Session
from app.core.network.session import kb256
from app.core.osio import AsyncOSFile


class DownloadPlan(msgspec.Struct, gc=False, frozen=True):
    url: str
    max_retry: int = 5
    headers: dict | None = None

    estimated_size: int | None = None

    target: str | PathLike | None = None
    targets: Iterable[str | PathLike] | None = None

    cache_name: str | None = None
    id: str | None = None

    link_mode: Literal['hardlink', 'symlink', 'copy'] = 'symlink'


def _link_file(src, dst, mode: Literal['hardlink', 'symlink', 'copy']):
    match mode:
        case 'hardlink':
            os.link(src, dst)
        case 'symlink':
            os.symlink(src, dst)
        case 'copy':
            shutil.copy2(src, dst)



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

    async def _download_single(
            self,
            url: str,
            filename: str | PathLike,
            progress: TaskProgress,
            headers: dict[str, str] | None = None,
    ):
        headers = headers or {}

        if progress.progress != 0:  # 仅在已有进度的时候才设置 range 头
            headers['Range'] = f'bytes={progress.progress}-'  # 一般来说，这个代码总会被执行一次

        logger.info(f"针对 {url!r} 的下载：即将发送请求, headers={headers!r}")

        response = await self.session.request('GET', url, headers=headers, stream=True)
        resp_time = time.monotonic()

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
                    buffer_size=114514,
                    executor=self.executor
            ) as f:
                if response.status_code != 206:  # 如果不是分片传输
                    await f.seek(0)
                    progress.progress = 0
                else:
                    await f.seek(progress.progress)

                stream_time = time.monotonic()
                async for chunk in await response.iter_content(kb256):
                    await f.write(chunk)
                    progress += len(chunk)
                    cnt += 1

                    if cnt % 16 == 0:
                        t = time.monotonic()
                        logger.debug(
                            "针对 {!r} 的下载（流报告）：收到的第 {} 个 chunk，当前进度：{} 距收到请求的时间：{} 距开始读取流的时间：{}",
                            url, cnt, progress.progress, t - resp_time, t - stream_time
                        )

                logger.debug("针对 {!r} 的下载：流读取已完成，正在截断和同步磁盘写入", url)

                await f.truncate(progress.progress)  # 砍掉后面的无用数据
                await f.sync()
        finally:
            await response.close()

    async def _download_wrapper(self, task, plan: DownloadPlan):
        sleep_time = 3

        url = plan.url
        headers = plan.headers
        max_retry = plan.max_retry

        logger.debug("已创建下载任务：{}", plan)

        single_target = plan.target
        if not plan.cache_name:
            assert single_target

        for i in range(max_retry + 1):
            try:
                logger.info("正在重试 （{!r}） {}/{}", url, i, max_retry)
                logger.debug(
                    "针对 {url!r} 的下载：排队中 重试次数：({i}/{max_retry})",
                    url=url, i=i, max_retry=max_retry
                )
                async with self.semaphore:
                    if plan.cache_name:
                        with self.file_cacher.open(plan.cache_name) as file:
                            await self._download_single(url, file, task, headers)
                            # 下载完成，创建链接，将位于缓存中的文件链接到目标（软链接）
                            mode = plan.link_mode
                            logger.info(
                                "来自 {!r} 的文件的链接方式：{}",
                                url, mode
                            )
                            if single_target:
                                _link_file(file, single_target, mode)

                            if plan.targets:
                                for target in plan.targets:
                                    _link_file(file, target, mode)

                    else:
                        await self._download_single(url, single_target, task, headers)
                return

            except HTTPError as e:
                if 500 > e.response.status_code >= 400:
                    logger.info("针对 {!r} 的下载：收到客户端错误，将在 {} 后重试", url, sleep_time)
                    await asyncio.sleep(sleep_time)
                    sleep_time *= 2
                else:
                    logger.warning(
                        f"针对 {url!r} 的下载：收到错误 {e}"
                    )

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

    def create_task(self, plan: DownloadPlan):
        progress = TaskProgress()
        progress.task = asyncio.create_task(  # type: ignore
            self._download_wrapper(progress, plan))
        return progress
