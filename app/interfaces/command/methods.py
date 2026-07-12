import builtins
import os
from pathlib import Path

import typer
from loguru import logger
from msgspec import Struct

from app.core.common import read_model, FileInfo
from app.core.common.config import cfg
from app.core.common.file_validator import FileValidator
from app.core.i18n import tr
from app.core.cacher.model_cacher import CacheManager
from app.core.resources.repository import Repository
from app.interfaces.command.common import console, session



def find_repo(repo, ask=True, raise_for_unset=False):
    if repo is None:
        repo = Path.cwd()
        if repo.name == '.minecraft':
            pass  # 直接到最后的返回 Repository 实例
        elif (repo / ".minecraft").is_dir():  # 如果工作目录下有 .minecraft 文件夹，那么直接使用
            repo = repo / '.minecraft'

        elif cfg.get('repo'):  # 否则尝试从配置文件中加载默认的存储库位置
            repo = cfg['repo']

        elif ask:  # 都找不到，向用户询问该不该本地创建存储库
            typer.confirm(tr("未发现且没有指定 Minecraft 储存库位置, 在本地创建存储库? "), abort=True)
            minecraft = Repository(repo / '.minecraft')
            minecraft.ensure_exists()
            return minecraft

        else:  # 指定了不应该询问，此时已经没有其它办法获取到存储库位置
            if raise_for_unset:  # 如果指定了无法找到时抛出错误
                raise RuntimeError("未指定 Minecraft 储存库")
            return None  # 否则返回 None

    return Repository(repo)  # 找到了的情况，返回 Repository 实例


async def call_and_cache[T: Struct](
        url: str,
        type: builtins.type[T],
        name: str,
        cacher: CacheManager, key: str,
        no_cache: bool = False,
        echo: bool = True
):
    logger.info("尝试获取资源 url={}, key={}, name={}", url, key, name)
    if not no_cache and (cache := cacher.get(key, type)):
        logger.info("已从缓存中获取结果")
        console.note(tr("使用已缓存的{}", name))
        return cache

    if echo:
        with console.status(tr("获取{}", name)):
            value = await session.call(url, type=type)

            if not no_cache:
                cacher.set(key, value)

            return value
    else:
        logger.info(f"缓存无效或被禁用，已开始下载")
        value = await session.call(url, type=type)

        if not no_cache:
            cacher.set(key, value)

        return value


async def check_or_call[T: Struct](
        url: str,
        type: builtins.type[T],
        name: str,
        validator: FileValidator,
        local: str | os.PathLike[str],
        sha1: str | None = None, size: int | None = None,
        echo: bool = True
):
    logger.info("尝试获取资源 url={}, local={}, name={}, sha1={}", url, local, name, sha1)

    if (
            await validator.validate(
                FileInfo(
                    filename=local,
                    size=size,
                    hash=sha1,
                    algorithm='sha1'
                )
            )
    ).result:  # 验证通过
        console.note(tr("使用验证后的本地文件{}", name))
        return read_model(local, type)

    else:
        if echo:
            with console.status(tr("获取{}", name)):
                return await session.call_into(url, local, type)
        else:
            return await session.call_into(url, local, type)


async def status(task, *, content, console):
    with console.status(content):
        return await task
