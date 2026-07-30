import builtins
import os
from pathlib import Path

import typer
from loguru import logger
from msgspec import Struct
from rich.columns import Columns
from rich.panel import Panel

from app.core.cacher.model_cacher import CacheManager
from app.core.common import read_model, RepositoryNotFound, ExceptionForUser
from app.core.configs import cfg
from app.core.file_validator import FileValidator
from app.core.i18n import tr
from app.core.minecraft.resources.repository import Repository
from app.core.models import FileInfo
from app.interfaces.commandline.base.console_extensions import console, session


# def find_repository(maybe_path, ask=True, raise_for_unset=False):
#     logger.info(f"查找储存库中, 提供参数 maybe_path={maybe_path!r}, ask={ask}, raise_for_unset={raise_for_unset}")
#     if maybe_path is None:
#         maybe_path = Path.cwd()
#         if maybe_path.name == '.minecraft':
#             logger.info(f"已找到(工作文件夹), 位置: {maybe_path}")
#             pass  # 直接到最后的返回 Repository 实例
#         elif (maybe_path / ".minecraft").is_dir():  # 如果工作目录下有 .minecraft 文件夹，那么直接使用
#             maybe_path /= '.minecraft'
#             logger.info(f"已找到(工作文件夹下), 位置: {maybe_path}")
#             pass
#
#         # elif cfg.get('repo'):  # 否则尝试从配置文件中加载默认的存储库位置
#         #     repo = cfg['repo']
#
#         elif ask:  # 都找不到，向用户询问该不该本地创建存储库
#             logger.info("将向用户发出询问")
#             result = typer.confirm(tr("未发现且没有指定 Minecraft 储存库位置, 在本地创建存储库? "))
#             logger.info(f"已向用户发出询问, 结果: {result}")
#
#             if not result and raise_for_unset:
#                 logger.error("用户取消输入, 抛出错误 RepositoryNotFound (For User)")
#                 raise ExceptionForUser(RepositoryNotFound())
#
#             logger.info(f"已在本地创建储存库 {maybe_path / '.minecraft'}")
#             minecraft = Repository(maybe_path / '.minecraft')
#             minecraft.ensure_exists()
#             return minecraft
#
#         else:  # 指定了不应该询问，此时已经没有其它办法获取到存储库位置
#             if raise_for_unset:  # 如果指定了无法找到时抛出错误
#                 logger.error("无法获取到储存库, 抛出错误 RepositoryNotFound (For User)")
#                 raise ExceptionForUser(RepositoryNotFound())
#             return None  # 否则返回 None
#
#     else:
#         logger.info("已提供路径, 不进行验证, 直接返回")  # TODO 我们是不是该检查一下呢
#
#     return Repository(maybe_path)  # 找到了的情况，返回 Repository 实例

def find_repository(maybe_path, abort=False):
    cwd = Path.cwd()

    if maybe_path is None:
        # 从 config 中加载
        select = cfg.get_selected_repository()
        if select:
            return Repository(select.path)

        elif (cwd / '.minecraft').is_dir():
            console.print(tr("将使用位于工作目录下的储存库"))
            return Repository(cwd / '.minecraft')
        elif abort:
            console.error(tr("未指定储存库位置"))
            raise typer.Abort()
        else:
            return None

    else:
        try:
            repo = cfg.get_repository(maybe_path)  # 尝试把 maybe_path 当成名称解析

            if not os.path.isdir(repo.path):
                console.error(tr("选中的储存库已失效"))
                if abort:
                    raise typer.Abort()

                return None

            return Repository(repo.path)
        except ValueError:
            # 尝试当作路径解析
            if os.path.isdir(maybe_path):
                return Repository(maybe_path)
            elif abort:
                raise typer.Abort()
            else:
                return None





async def call_and_cache[T: Struct](
        url: str,
        type: builtins.type[T],
        name: str,
        cacher: CacheManager, key: str,
        no_cache: bool = False,
        echo: bool = True
):
    logger.info("尝试从缓存或网络获取资源 url={}, key={}, name={}", url, key, name)
    if not no_cache and (cache := cacher.get_model(key, type)):
        logger.info("已从缓存中获取结果")
        console.note(tr("使用已缓存的{}", name))
        return cache

    logger.info(f"缓存无效或已被禁用，已开始下载")
    if echo:
        with console.status(tr("获取{}", name)):
            value = await session.call(url, type=type)

            if not no_cache:
                cacher.set_model(key, value)

            return value
    else:
        value = await session.call(url, type=type)

        if not no_cache:
            cacher.set_model(key, value)

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


def make_multi_shower(values, title, style='', border_style='none'):
    return Panel(
        title=title,
        style=style,
        border_style=border_style,
        renderable=Columns(
            values,
            expand=True, equal=True
        )
    )
