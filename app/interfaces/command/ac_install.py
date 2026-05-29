import asyncio
import os.path
from asyncio import Semaphore
from pathlib import Path
from typing import overload, Any, Literal

import psutil
import typer
from loguru import logger

from app.common.concurrent_ import as_sync, reset_max_processes
from app.common.config import cfg
from app.common.hash_computer import check_hash
from app.common.methods import dotpath, read_json, write_json
from app.i18n import tr
from app.interfaces.command.common import typer_app, console
from app.interfaces.command.methods import get_version_manifest
from app.network.download_task import DownloadTask
from app.network.session import session
from app.resources.assets import AssetsDirectory
from app.resources.base import rules_matcher, RulesMatcher
from app.resources.libraries import LibrariesDirectory
from app.resources.repository import Repository


async def process_assets(objects, assets_directory: AssetsDirectory):
    total_size = 0
    requires = set()

    async def proc_asset(obj):
        nonlocal total_size
        if obj['hash'] in requires:
            return

        if not await assets_directory.check(obj['hash']):
            logger.info(f"Need {obj['hash']}")
            requires.add(obj['hash'])
            total_size += obj['size']

    await asyncio.gather(*map(proc_asset, objects.values()))

    return total_size, requires


async def process_libraries(libraries, ld: LibrariesDirectory, matcher: RulesMatcher):
    total_size = 0
    requires = set()

    async def proc_library(lib: dict):
        nonlocal total_size

        if natives := lib.get('natives'):  # 如果是一个本地库
            # console.print("发现本地库", lib['name'], natives)
            classifier = natives[matcher.os_name]  # 从当前系统名称获取到分类名
            download_info = dotpath(  # 获取这个分类的下载信息
                lib, f"downloads.classifiers.{classifier}"
            )
            lib_name = f"{lib['name']}:{classifier}"  # 组合库名（完整）
            if not await ld.check(lib_name, download_info['sha1']):  # 尝试检查这个库存不存在
                requires.add(lib_name)  # 不存在，加入到处理列表中
                total_size += download_info['size']  # 累计总大小

        try:  # 旧版的 Minecraft 的某些库没有提供通用的 artifact
            download_info = dotpath(lib, "downloads.artifact")
            if not await ld.check(lib['name'], download_info['sha1']):
                requires.add(lib['name'])
                total_size += download_info['size']
        except KeyError as e:
            if str(e.args[0]) != 'artifact':
                raise e

    async with asyncio.TaskGroup() as tg:
        for lib in libraries:
            if (rules := lib.get('rules')) and not matcher.match(rules):
                continue

            tg.create_task(proc_library(lib))

    return total_size, requires


async def process_main_file(client_info, filename):
    hash = client_info['sha1']
    size = client_info['size']

    if os.path.exists(filename) and await check_hash(filename, hash):
        return 0, None
    else:
        return size, client_info['url']


@overload
def find_repo(repo: Any, ask: bool = True, raise_for_unset: Literal[True] = True) -> Repository: ...


@overload
def find_repo(repo: Any, ask: bool = True, raise_for_unset: Literal[False] = False) -> Repository | None: ...


def find_repo(repo, ask=True, raise_for_unset=False):
    if repo is None:
        repo = Path.cwd()
        if (repo / ".minecraft").is_dir():
            repo = repo / '.minecraft'

        elif cfg.get('repo'):
            repo = cfg['repo']

        elif ask:
            typer.confirm(tr("未发现且没有指定 Minecraft 储存库位置, 在本地创建存储库? "), abort=True)
            repo = repo / '.minecraft'

        else:
            if raise_for_unset:
                raise RuntimeError("未指定 Minecraft 储存库")
            return None

    return Repository(repo)


@typer_app.command()
@as_sync
async def install(
        name: str,
        version: str | None = typer.Option(None, '-v', "--version"),
        repo: Path | None = typer.Option(None, '-r', "--repo"),
        max_threads: int = typer.Option((psutil.cpu_count() or 4), '-m', "--max-threads"),
        yes: bool = typer.Option(False, '-y', "--yes"),
        max_connections: int = typer.Option(64, '-M', "--max-connections")
):
    """
    安装版本
    """

    reset_max_processes(max_threads)

    minecraft = find_repo(repo, raise_for_unset=True)
    minecraft.ensure_exists()

    if version is None:
        version = name

    # 创建版本实例
    target_instance = minecraft.versions.instance(name)
    if target_instance.check():
        typer.confirm((tr(
            "名为 `{name}` 的实例({version})已存在，是否覆盖？", name=name, version=target_instance.id)),
            abort=True
        ) if not yes else None
    else:
        target_instance.ensure_exists()

    async with session:
        with minecraft.launcher_data.cache.get('version-manifest') as cache_file:
            cache_file.max_age = 300  # seconds
            if cache_file.is_valid():
                console.note(tr("使用缓存的版本清单"))
                manifest = cache_file.read_json()
            else:
                manifest = await get_version_manifest()
                write_json(cache_file, manifest)
                cache_file.set()

        # 特殊版本号处理
        if version == 'latest':
            version = dotpath(manifest, 'latest.release')
        elif version == "latest-snapshot":
            version = dotpath(manifest, 'latest.snapshot')

        # 查找关于这个版本的记录
        version_desc_url = None
        for version_desc_record in manifest['versions']:
            if version_desc_record['id'] == version:
                version_desc_url = version_desc_record['url']
                break

        if version_desc_url is None:
            raise RuntimeError(tr("无法找到版本 {name}", name=version))

        # 2. 下载版本描述文件
        with console.status(tr("获取版本描述文件")), minecraft.launcher_data.cache.get(
                f'version-desc:{version}') as cache_file:
            if cache_file.is_valid():
                console.note("使用缓存的版本描述文件")
                cache_file.linkto(target_instance.desc_file, force=True)
                version_desc = read_json(cache_file)
            else:
                version_desc = await session.call_file_based(version_desc_url, cache_file.file)
                cache_file.set(cache_file.file)

        asset_index_name = version_desc['assets']
        asset_index_file = minecraft.assets.indexes.fullpath(asset_index_name)

        with console.status(tr("获取资源文件索引")):
            if not (  # 如果资源索引不存在或者校验没通过
                    asset_index_file.exists() and
                    await check_hash(asset_index_file, version_desc['assetIndex']['sha1'])
            ):
                asset_index = await session.call_file_based(
                    url=version_desc['assetIndex']['url'],
                    filename=asset_index_file,
                )

            else:
                asset_index = read_json(asset_index_file)

        # 3. 分析游戏文件
        with console.status(tr("分析游戏文件")):
            (
                (assets_total_size, required_assets),
                (libraries_total_size, required_libraries),
                (main_jar_size, main_jar_url)
            ) = await asyncio.gather(
                process_assets(asset_index['objects'], minecraft.assets),
                process_libraries(version_desc['libraries'], minecraft.libraries, matcher=rules_matcher),
                process_main_file(version_desc['downloads']['client'], target_instance.main_file)
            )

            # 汇总信息
            total_size = assets_total_size + libraries_total_size + main_jar_size
            total_files = len(required_assets) + len(required_libraries) + bool(main_jar_url is not None)

        if not total_files:  # 没有文件需要下载或者处理
            console.print(tr("版本已正确安装"))
            raise typer.Exit()  # 结束

        console.print(tr("需要下载的文件: {files}\t\t需要下载的大小: {size}", files=total_files, size=total_size))
        console.print(tr(
            "资源文件：{assets_count}\t\t库文件：{libraries_count}\t\t主文件：{main_jars_count}",
            assets_count=len(required_assets),
            libraries_count=len(required_libraries),
            main_jars_count=int(bool(main_jar_url)),
        ))
        typer.confirm(tr("确定? "), abort=True) if not yes else None

        sem = Semaphore(max_connections)
        async with tm:
            if main_jar_url:
                tm.add_task(DownloadTask(
                    url=main_jar_url,
                    filename=target_instance.main_file,
                    sem=sem, description=tr("主文件 {name}", name=version + '.jar'), session=session
                ))

            for asset in required_assets:
                tm.add_task(DownloadTask(
                    url=f"https://resources.download.minecraft.net/{asset[:2]}/{asset}",
                    filename=minecraft.assets.objects.asset(asset),
                    sem=sem, description=tr("资源文件 {name}", name=asset), session=session
                ))

            for library in required_libraries:
                tm.add_task(DownloadTask(
                    url=f"https://resources.download.minecraft.net/{library[:2]}/{library}",
                    filename=minecraft.libraries.library(library).fullpath,
                    sem=sem, description=tr("库文件 {name}", name=library), session=session
                ))


        # 5. 完成!!!
        console.print(tr("Version {id} installed successfully", id=name))
