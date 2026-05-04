import asyncio
import os.path
import shutil
import time
from pathlib import Path

import psutil
import rich.progress
import typer
from loguru import logger
from orjson import orjson
from rich.progress import TextColumn, BarColumn, FileSizeColumn, TotalFileSizeColumn, TransferSpeedColumn, \
    TimeRemainingColumn

from app.common.concurrent_ import as_sync, reset_max_threads
from app.common.config import cfg
from app.common.hash_computer import check_hash
from app.common.methods import dotpath, read_json
from app.i18n import tr
from app.interfaces.command.common import typer_app, assert_, console
from app.interfaces.command.methods import get_version_manifest
from app.network.session import session
from app.resources.assets import AssetsDirectory
from app.resources.base import rules_matcher, RulesMatcher
from app.resources.libraries import LibrariesDirectory
from app.resources.repository import Repository

progress_bar = rich.progress.Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    FileSizeColumn(),
    TotalFileSizeColumn(),
    TransferSpeedColumn(),
    TimeRemainingColumn(),
)


class TaskManager:
    def __init__(self, max_tasks: int, total=None):
        self.progress_bar = rich.progress.Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            FileSizeColumn(),
            TotalFileSizeColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        )
        self.sem = asyncio.Semaphore(max_tasks)
        self.progress_total = self.progress_bar.add_task("Total", total=total)
        self.tg = asyncio.TaskGroup()

    def set_total(self, total):
        self.progress_bar.update(self.progress_total, total=total)

    async def download(self, url: str, filename: str, description: str | None = None):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)  # 保证文件路径存在

        progress = 0  # 下载完成部分的大小
        task_id = None  # 如果创建了进度条，它就是一个 TaskID 实例

        for i in range(5):  # 一共尝试 5 次
            try:
                async with self.sem:  # 并发限制
                    with open(filename, 'ab') as f:  # 追加模式打开，防止意外清除下载进度
                        f.seek(progress)  # 导航到完成的位置
                        f.truncate()  # 截取掉后面的无效数据

                        stream, resp = await session.stream_(
                            url, 65536, headers={'Range': f'bytes={progress}-'},
                            errorcheck=lambda x: x.status_code == 206
                        )  # 发送下载请求，包含 Range 头部实现断点续传
                        total_size = int(resp.headers.get('Content-Length', 0))
                        start_time = time.time()  # 记录本次下载的起始时间
                        async for chunk in stream:
                            f.write(chunk)

                            progress += len(chunk)

                            # 计算剩余时间
                            time_remaining = total_size / (progress / (time.time() - start_time))

                            if task_id is not None:  # 如果创建了进度条，那么更新它
                                self.progress_bar.update(task_id, completed=progress)

                            elif time_remaining > 5:  # 如果没有创建进度条，剩余时间大于 5s，创建进度条
                                task_id = self.progress_bar.add_task(description or '', total=total_size,
                                                                     completed=progress)

                            self.progress_bar.advance(self.progress_total, len(chunk))

                if task_id is not None:
                    self.progress_bar.remove_task(task_id)  # 完成后删除进度条

                logger.info(f"Downloading finished {url}")
                return

            except Exception as e:
                logger.warning(f"Error when downloading {url}, exception: {e.__class__.__name__}: {e}")
                # console.print_exception()

        # 五次都没有下载成功
        raise RuntimeError(f"Cannot download {filename}")

    def create_task(self, url: str, filename: str, description: str | None = None):
        self.tg.create_task(self.download(url, filename, description))

    async def __aenter__(self):
        self.progress_bar.__enter__()
        return await self.tg.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.tg.__aexit__(exc_type, exc_val, exc_tb)
        self.progress_bar.__exit__(exc_type, exc_val, exc_tb)


async def process_assets(objects, assets_directory: AssetsDirectory):
    total_size = 0
    requires = []

    async def proc_asset(obj):
        nonlocal total_size

        if not await assets_directory.check(obj['hash']):
            requires.append(obj['hash'])
            total_size += obj['size']
            # print('require', obj['hash']）

    await asyncio.gather(*map(proc_asset, objects.values()))

    return total_size, requires


async def process_libraries(libraries, ld: LibrariesDirectory, matcher: RulesMatcher = None):
    total_size = 0
    requires = []

    if matcher is None:
        matcher = rules_matcher

    async def proc_library(lib):
        nonlocal total_size

        if natives := lib.get('natives'):  # 处理本地库
            classifier = natives[matcher.os_name]  # 从当前系统名称获取到分类名
            download_info = dotpath(  # 获取这个分类的下载信息
                lib, f"downloads.classifiers.{classifier}"
            )
            lib_name = lib['name'] + ':' + classifier  # 组合库名（完整）
            if not await ld.check(lib_name, download_info['sha1']):  # 尝试检查这个库存不存在
                requires.append(lib_name)  # 不存在，加入到处理列表中
                total_size += download_info['size']  # 累计总大小

        try:  # 旧版的 Minecraft 的某些库没有提供通用的 artifact
            download_info = dotpath(
                lib, "downloads.artifact"
            )
            if not await ld.check(lib['name'], download_info['sha1']):
                requires.append(lib['name'])
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


def find_repo(repo, ask=True):
    if repo is None:
        repo = Path.cwd()
        if (repo / ".minecraft").is_dir():
            repo = repo / '.minecraft'

        elif cfg.get('repo'):
            repo = cfg['repo']

        elif ask:
            typer.confirm(tr("未发现且没有指定 Minecraft 储存库位置, 在本地创建储存库? "), abort=True)
            repo = repo / '.minecraft'
            return repo

        else:
            return None

    return repo


@typer_app.command()
@as_sync
async def install(
        name: str,
        version: str | None = typer.Option(None, '-v', "--version"),
        modloader: str | None = typer.Option(None, '-l', "--modloader"),
        repo: Path | None = typer.Option(None, '-r', "--repo"),
        max_threads: int = typer.Option((psutil.cpu_count() or 4) * 2, '-m', "--max-threads"),
        max_connections: int = typer.Option(64, '-M', "--max-connections"),
        offline: bool = typer.Option(False, '-F', "--offline"),
):
    """
    安装版本
    """

    reset_max_threads(max_threads)

    if modloader:
        raise NotImplementedError("Mod loader support not implemented")  # TODO: Finish me
        modloader = modloader.lower()
        assert_(modloader in ["forge", "fabric", "neoforge"])

    repo = find_repo(repo)

    # 初始化储存库对象
    minecraft = Repository(repo)

    if version is None:
        version = name

    # 创建版本实例
    instance = minecraft.versions.instance(name)
    if instance.check():
        typer.confirm((tr(
            "名为 `{name}` 的实例({version})已存在，是否覆盖？", name=name, version=instance.id)),
            abort=True
        )
    else:
        instance.ensure_exists()

    async with session:
        if not offline:  # 离线安装时无法从官方源获取清单等信息
            manifest = await get_version_manifest()

            # 特殊名称处理
            if name == 'latest':
                name = dotpath(manifest, 'latest.release')
            elif name == "latest-snapshot":
                name = dotpath(manifest, 'latest.snapshot')

            # 查找关于这个版本的记录
            version_desc_url = None
            for item in manifest['versions']:
                if item['id'] == version:
                    version_desc_url = item['url']
            if version_desc_url is None:
                raise RuntimeError(tr("无法找到版本 {name}", name=version))

        else:  # 离线模式安装的特殊处理
            try:
                local_instances = minecraft.versions.mapping
                instances = local_instances[version]
                console.print(tr("本地找到的版本相同的实例如下"))
                console.print()
                for ins in instances:
                    console.print('  [green]*[/green]', ins.name)
                console.print()
                console.print(tr("我们将选择第一个版本"))

                source_instance = instances[0]
                version_desc = source_instance.desc
                with console.status(tr("同步实例信息")):
                    shutil.copy2(source_instance.desc_file, instance.desc_file)

            except KeyError:
                console.print(
                    tr(f"[red]本地没有找到为[/red] {version} [red]的版本，离线安装需要一个相同版本且已安装的实例[/red]"))
                raise typer.Exit(1)
        # Offline Process End

        # 2. 下载版本描述文件
        if not offline:  # 下载只在在线安装时有用
            with console.status(tr("获取版本描述文件")):
                version_desc = await session.call(version_desc_url)
        # else:
        #     pass  # 离线时的版本描述文件已经被提前处理了
        #           # line to: 253

        # 这里一部分逻辑不需要区分在线不在线
        asset_index_name = version_desc['assets']
        asset_index_file = minecraft.assets.index_filename(asset_index_name)

        if not (  # 如果资源索引不存在或者校验没通过
                minecraft.assets.index_exists(asset_index_name) and
                await check_hash(asset_index_file, version_desc['assetIndex']['sha1'])
        ):
            if not offline:  # 同理，离线模式不能下载
                with console.status(tr("获取资源文件索引")):  # 重新下载
                    asset_index = await session.call_file_based(
                        url=version_desc['assetIndex']['url'],
                        filename=asset_index_file,
                    )
            else:  # 如果运行到了这里，说明 asset index 已损坏
                console.print(tr("[red]致命错误：本地资源索引已损坏[/red]"))
                raise typer.Exit(1)

        else:
            asset_index = read_json(
                file=asset_index_file,
            )  # 这里无论在不在线都一样

        # 3. 分析游戏文件
        with console.status(tr("分析游戏文件")):  # 这里不需要区分在线不在线，都是直接转递的数据
            (
                (
                    assets_total_size, required_assets
                ),
                (
                    libraries_total_size, required_libraries
                ),
                (
                    main_jar_size, main_jar_url
                )
            ) = await asyncio.gather(
                process_assets(asset_index['objects'], minecraft.assets),
                process_libraries(version_desc['libraries'], minecraft.libraries, matcher=rules_matcher),
                process_main_file(version_desc['downloads']['client'], instance.main_file)
            )

            # 汇总信息
            total_size = assets_total_size + libraries_total_size + main_jar_size
            total_files = len(required_assets) + len(required_libraries) + bool(main_jar_url is not None)

        if not total_files:  # 没有文件需要下载或者处理
            console.print(tr("版本已正确安装"))
            raise typer.Exit()  # 结束

        if not offline:  # 只有在线的时候能下载，所以这里的消息要区分
            console.print(tr("需要下载的文件: {files}\t\t需要下载的大小: {size}", files=total_files, size=total_size))
            typer.confirm(tr("确定? "), abort=True)
        else:  # 离线还需要下载文件的话，可能是主文件没有处理到
            if not main_jar_url:  # 无需下载主文件，说明其它文件有问题，离线安装无能为力
                console.print(tr("[red]致命错误：本地缺失安装此版本的文件[/red]"))
                console.print(tr("资源文件："), tr(f"{len(required_assets)} 个"))
                console.print(tr("库文件："), tr(f"{len(required_libraries)} 个"))
                console.print(tr("主文件："), tr(f"{int(bool(main_jar_url))} 个"))
                raise typer.Exit(1)  # 报错，退出
            else:
                # 尝试 copy 一个主文件过来
                with console.status(tr("从源版本中提取主文件")):
                    shutil.copy2(source_instance.main_file, instance.main_file)
                    # 出现异常直接 raise 就行了，不管他

                console.print("[green]离线安装成功！[/green]")
                raise typer.Exit(0)  # OK

        # 4. 下载文件，如果是离线安装，这里不会被执行

        tm = TaskManager(max_connections, total=total_size)  # 创建任务管理器，它会自动处理下载进度的显示和更新
        async with tm:
            if main_jar_url:  # 如果需要下载 主文件 （如果不需要，那么 main_jar_url 将会为 None
                tm.create_task(
                    url=main_jar_url,
                    filename=instance.path / (name + '.jar'),
                    description=tr("主文件：{name}", name=name + '.jar')
                )

            for asset in required_assets:  # 添加资源文件的下载任务
                tm.create_task(
                    url=f"https://resources.download.minecraft.net/{asset[:2]}/{asset}",
                    filename=minecraft.assets.asset(asset),
                    description=tr("资源文件：{hash}", hash=asset)
                )

            for lib_name in required_libraries:  # 添加依赖库的下载任务
                lib_path = minecraft.libraries.library(lib_name).path.replace('\\', '/')
                tm.create_task(
                    url=f"https://libraries.minecraft.net/{lib_path}",
                    filename=minecraft.libraries.path / lib_path,
                    description=tr("依赖库：{name}", name=lib_name)
                )

        # 5. 完成!!!
        console.print(tr("Version {id} installed successfully", id=name))
