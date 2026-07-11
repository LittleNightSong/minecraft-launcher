import asyncio
import os
from asyncio import Semaphore, AbstractEventLoop
from concurrent.futures import Executor
from os import PathLike

from httpx import HTTPStatusError
from loguru import logger

from app.core.common.files.aio import AioFile
from app.core.common.task import TaskProgress
from app.core.network import Session
from app.core.network.session import kb256


class Downloader:  # FIXME
    def __init__(
            self,
            max_connections: int,
            executor: Executor,
            session: Session | None = None,
    ):
        self.session = session or Session()  # TODO: 外部不应该传入已使用的 session ，不然线程独立跨事件循环运行会出问题
        self.semaphore = Semaphore(max_connections)
        self.executor = executor

        # self.loop = asyncio.new_event_loop() # TODO 在线程从独立运行事件循环和处理下载，优先级：低
        self.loop: AbstractEventLoop = asyncio.get_event_loop()

    async def _download_single(
            self,
            url: str,
            filename: str | PathLike,
            progress: TaskProgress,
            headers: dict[str, str] | None = None,
    ):
        headers = headers or {}

        if progress.progress != 0:
            headers['Range'] = f'bytes={progress.progress}-'

        logger.debug(f"针对 {url!r} 的下载：即将发送请求, headers={headers!r}")

        response = await self.session.request('GET', url, headers=headers, stream=True)
        try:
            logger.info(f"针对 {url!r} 的下载：已收到响应 {response}")

            response.raise_for_status()

            if response.status_code == 200:
                progress.total = int(response.headers.get('content-length', 0))

            try:
                await self.loop.run_in_executor(
                    self.executor,
                    os.makedirs, os.path.dirname(filename)
                )
            except FileExistsError:
                pass

            async with AioFile.open(
                    filename,
                    os.O_WRONLY | os.O_CREAT | os.O_BINARY,
                    executor=self.executor
            ) as f:
                if response.status_code != 206:  # 不是分片传输
                    await f.seek(0)
                    progress.progress = 0
                else:
                    await f.seek(progress.progress)

                async for chunk in await response.iter_content(kb256 * 4):
                    await f.write(chunk)
                    progress += len(chunk)

                logger.debug(f"针对 {url!r} 的下载：流读取已完成，正在截断和同步磁盘写入")

                await f.truncate(progress.progress)
                await f.sync()
        finally:
            await response.close()

    async def _download_wrapper(self, task, url, filename, headers, max_retries):
        sleep_time = 3
        headers = headers or {}

        info = {'url': url, 'filename': filename, 'headers': headers, 'max_retries': max_retries}
        logger.debug(f"已创建下载任务：{info}")

        for i in range(max_retries + 1):
            try:
                logger.debug(f"针对 {url!r} 的下载：排队中 重试次数：({i}/{max_retries})")
                async with self.semaphore:
                    logger.debug(f"针对 {url!r} 的下载已开始")
                    await self._download_single(url, filename, task, headers)
                    logger.debug(f"针对 {url!r} 的下载已完成")
                return

            except HTTPStatusError as e:
                if e.response.is_client_error:
                    logger.warning(f"针对 {url!r} 的下载：收到客户端错误，将在 {sleep_time} 后重试")
                    await asyncio.sleep(sleep_time)
                    sleep_time *= 2
                else:
                    logger.warning(
                        f"针对 {url!r} 的下载：收到错误 {e}"
                    )

            except Exception as e:
                logger.opt(exception=e).warning(
                    f"针对 {url!r} 的下载"
                    f"（进度：{task.progress}/{task.total}，"
                    f"重试：{i}/{max_retries}）："
                    f"未知错误 ({e.__class__.__name__}) {e}")

        logger.error(
            f"针对 {url!r} 的下载：已达到最大重试次数({max_retries})，进度：{task.progress}/{task.total}"
        )

        raise RuntimeError(f"针对 {url!r} 的下载：已达到最大重试次数 {max_retries}")

    def create_task(self, url: str, filename: str | PathLike, headers: dict[str, str] | None = None, max_retries=5):
        progress = TaskProgress()
        progress.task = asyncio.create_task(  # type: ignore
            self._download_wrapper(progress, url, filename, headers, max_retries))
        return progress
