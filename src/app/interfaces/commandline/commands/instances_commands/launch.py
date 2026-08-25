import asyncio
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from string import Template
from typing import Literal

import psutil
import typer
from rich.console import Group
from rich.panel import Panel

from app.core.common import format_filesize
from app.core.common.zzipfile import extract_to
from app.core.configs import cfg, JavaRecord
from app.core.file_validator import res_false_filter, FileValidator
from app.core.i18n import tr
from app.core.java.size import parse
from app.core.memory_allocator import MemoryAllocator
from app.core.minecraft.directories import InstanceDirectory
from app.core.models import FileSpec, Library
from app.core.models.env import Environment
from app.core.models.launch_context import LaunchContext, JVMContext
from app.core.models.version_meta import VersionMeta, NativeLibraryStruct
from app.core.network import Session
from app.core.process_builder import ProcessBuilder
from app.third_party.mojang import MinecraftAPI
from app.interfaces.commandline import typer_app
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.methods import find_repository, status


# noinspection PyAttributeOutsideInit
class LaunchCommand(Command, app=typer_app):
    name = 'launch'

    async def check_all_files(self, ins: InstanceDirectory, meta: VersionMeta):

        files: list[tuple[str, FileSpec]] = []
        files.extend(
            self.repo.assets
            .read_index(meta.dependencies.assets_index.id)
            .iter_files(self.repo.assets.path)
        )
        files.extend(
            self.repo.libraries.get_library_files(
                libraries=meta.dependencies.libraries,
                env=self.env
            )
        )

        client = meta.downloads.client
        files.append((
            ins.main_file,
            FileSpec(
                size=client.size,
                checksum=client.sha1,
                algorithm='sha1',
            )
        ))

        return res_false_filter(
            await status(
                task=asyncio.gather(*[
                    self.file_validator.validate(*file)
                    for file in reversed(files)
                ]),
                content="校验文件中",
                console=console
            )
        )

    async def unzip_native_libraries(self, ins: InstanceDirectory, meta: VersionMeta):
        loop = asyncio.get_event_loop()
        env = self.env
        required_natives = [
            i for i in meta.dependencies.libraries
            if isinstance(i, NativeLibraryStruct)
            if i.pass_rules(env)
            if i.get_native_safe(env)
        ]
        # console.print(required_natives)
        tasks = [
            loop.run_in_executor(
                self.pool,

                extract_to,
                self.repo.libraries.path / i.get_native(env).path,
                ins.natives_dir
            )
            for i in required_natives
        ]
        await asyncio.gather(*tasks)

    async def init(self, repo):
        self.repo = find_repository(repo, abort=True)
        self.pool = ThreadPoolExecutor(max_workers=32)
        self.file_validator = FileValidator(executor=self.pool)
        self.session = Session()
        self.api = MinecraftAPI(self.session)
        self.env = Environment.new()

    async def main(
            self,
            name: str,
            *,
            username: str | None = None,
            usertype: Literal['online', 'offline', 'littleskin'] = 'offline',
            repo: Path | None = None,  # 这个参数在 init 中被处理
            memmax: str | None = typer.Option(None, '-M', '--memmax'),
            memmin: str | None = typer.Option(None, '-m', '--memmin'),

            quick_play: str | None = typer.Option(None, '-q', '--quick-play'),

            show_args: bool = False, show_uuid: bool = False
    ):
        """
        启动指定名称的实例

        :param name: 实例名称
        :param username: 用户名
        :param usertype: 登录方式
        :param repo: 存储库名称或者路径
        :param memmax: 游戏运行最大内存
        :param memmin: 游戏运行最小内存

        :param quick_play: 快速启动目标，格式为 [yellow]type[/]:[yellow]value[/]

        [yellow]type[/] 可选：[literal]save[/], [literal]server[/], [literal]realms[/]，分别控制快速进入的目标（本地存档、服务器、领域服务器）

        [yellow]value[/] 在不同的 [yellow]type[/] 中有不同的语义
            - [literal]save[/]: [yellow]value[/] 表示本地存档的名称
            - [literal]server[/]: [yellow]value[/] 表示服务器的地址，格式为 [bold cyan]host:port[/]，[yellow]port[/] 可以省略，默认为 [repr.number]25565[/]
            - [literal]realms[/]: （我不知道格式是啥）

        :param show_args: 是否输出游戏启动参数
        :param show_uuid: 是否显示用户的 UUID
        :return:
        """
        env = self.env
        ins: InstanceDirectory = self.repo.versions.instance(name)
        if not ins.is_valid():
            console.error(tr("指定的版本不存在"))
            raise typer.Abort()

        meta = ins.version_meta

        # 校验所有资源
        result = await self.check_all_files(ins, meta)
        if result:
            console.print(result)
            console.error(tr("版本文件存在问题，请使用 [green]install[/green] 修复后再启动"))
            raise typer.Abort()

        if username is None:
            username = console.prompt("输入游玩时使用的用户名：", abort=True)

        # 检查一下名字的长度
        if len(username) > 16:  # 1.20.3 起限制长度只能是 16 字符, 我们这里可能接触到快照版, 不好判断, 干脆不处理了...
            console.warning("您的用户名长度大于 16, 游玩 [version]1.20.3[/] 以上版本将无法进入游戏")

        # 再检测一下有没有不在官方给的允许字符中的字符
        if re.match(r'[^a-zA-Z0-9_]', username):
            console.warning("用户名包含特殊字符, 游玩 [version]1.18[/] 以上版本时将无法进入游戏")

        console.print()

        # 处理登录  # TODO: 支持正版登录和第三方登录
        match usertype:
            case 'offline':
                uuid = self.api.calc_player_uuid(username)
                token = 'FFFF'
                xuid = 'none'
                clientid = 'none'
            case _:
                console.error(f"不支持的用户类型 {usertype}")
                raise typer.Abort()

        console.print(f"登录成功 (模式 [yellow bold]{usertype}[/]), 您的用户名为 {username}")
        if show_uuid:
            console.print(tr("[dim]UUID {}[/dim]", uuid))

        # 拼接 classpath
        libraries = ins.version_meta.dependencies.libraries
        # console.print(libraries)
        classpath_list = {
            Library(file.name).deduplication_key: str(self.repo.libraries.path / file.path)
            for lib in libraries
            for file in lib.collect(env)
        }

        # 记得加上 Minecraft 主 jar
        classpath_list['main'] = (str(ins.main_file))

        classpath_sep = ';' if os.name == 'nt' else ':'  # 不同的系统使用不同的分隔符
        classpath = classpath_sep.join(classpath_list.values())

        ctx = LaunchContext(  # 构建启动上下文
            username=username,
            version_name=ins.mojang_version_meta.id,
            version_type='',
            game_dir=ins.path,
            assets_dir=self.repo.assets.path,
            assets_index_name=ins.mojang_version_meta.assets,

            uuid=uuid,
            token=token,
            clientid=clientid,
            xuid=xuid,

            natives_dir=ins.natives_dir,
            launcher_name='clcl',  # 启动器名称 # TODO：使用全局常量
            launcher_version=str(114514),

            classpath=classpath,

            classpath_sep=classpath_sep,  # 这玩意干啥用的来着？
            libraries_directory=self.repo.libraries.path
        )

        if quick_play is not None:  # 解析快速游玩字符串
            type_, value = quick_play.split(':', 1)  # 以 : 为界，分割 type 和 value
            match type_:
                case 'save':
                    ctx.quick_play_single_player = value  # 自动进入本地存档
                case 'server':
                    ctx.quick_play_multi_player = value # 自动进入远程服务器
                case 'realm':
                    ctx.quick_play_realms = value  # 自动进入微软的 Realms 服务器 # TODO：检查是否是正版登录
                case _:
                    console.error(tr("不支持的快速启动目标类型：{}", type_))
                    raise typer.Abort()

        features = ctx.generate_features().to_dict()
        context_dict = ctx.to_dict()

        memory_info = psutil.virtual_memory()  # 获取和计算内存信息
        available_memory = memory_info.available

        if memmax is None:
            allocator = MemoryAllocator()
            memmax = allocator.allocate(available_memory)  # 提前把 allocator 返回的字节数转换成字符串

            if memmax < 2097152:  # 16Mib
                console.error(tr("可用内存太小, 无法分配所需的内存"))  # 这个值有点极端，一般来说，16Mb 不够支撑我的世界的运行
                raise typer.Abort()

            if memmax <= 1024 ** 3:  # 1GB
                console.warning(tr("分配的内存较小，可能导致游戏卡顿"))

        else:
            memmax = parse(memmax)

            if memmax > available_memory:
                console.warning(tr(
                    "尝试分配的内存 {} 超过了系统可用内存，自动降低为 {}",
                    format_filesize(memmax),
                    format_filesize(available_memory)
                ))
                memmax = available_memory

        console.print(
            '\n',
            tr(
                "系统总内存 {}, 可用内存 {}, 实际分配内存 {}",
                format_filesize(memory_info.total),
                format_filesize(memory_info.available),
                format_filesize(memmax)
            ),
            sep=''
        )

        jvm_ctx = JVMContext(  # 构建自定义 jvm 上下文
            mem_min=memmin or '16M', mem_max=memmax
        )

        builder = ProcessBuilder()
        builder |= ins.path  # 设置工作目录在版本文件夹中

        # 设置 java executable 位置
        # 需要找到一个最接近要求的 java

        # 首先获取所有适合的 Java (所有 major 版本大于版本要求的)
        suitable_javas: list[JavaRecord] = list(cfg.get_javas_forward(ins.mojang_version_meta.java_version.major_version))

        if not suitable_javas:  # 没有符合要求的 java
            console.error(tr("找不到适合的 Java 版本"))
            raise typer.Abort()

        # 排个序, 从小到大排（这是为了最好的兼容性），即可以尽可能保留兼容性，还可以动态回滚到第二接近、第三接近的 java 版本
        suitable_javas.sort(key=lambda r: r.major)
        # 找第一个并设置为启动时使用的 java
        chosen_java = None

        for candy in suitable_javas:
            if os.path.exists(candy.path):
                chosen_java = candy
                break

        if chosen_java is None:  # 如果保存的 java 列表中没有有效的 java
            console.error("本地无有效 Java")
            raise typer.Abort()

        builder <<= chosen_java.javaw_path()  # 设置 java executable

        console.print(tr(
            "已选择位于 [path]\"{}\"[/] 的 [java]java {}[/]", chosen_java.path, chosen_java.major),  # 跟用户喊一声
            highlight=False
        )
        # console.tip(tr("Java 主版本: {}", chosen_java.major))

        with console.status('解压本地库文件'):
            await self.unzip_native_libraries(ins, meta)

        jvm_arguments = meta.arguments.format_jvm_args(context_dict, env, features)  # 从官方的规则中获取 jvm 参数
        game_arguments = meta.arguments.format_game_args(context_dict, env, features)

        jvm_extension_arguments = [  # 暂无  # 由启动器自己自动添加的参数
        ]

        builder += jvm_extension_arguments  # 启动器给的参数优先级最小
        builder += jvm_arguments  # 随后是游戏给出的(虽然老版本中他也是启动器生成的，无伤大雅)
        builder += jvm_ctx.to_args()  # 接下来是配置参数, 这个参数和其它参数基本不冲突
        builder += meta.main_class  # 放主类, 主类之后就是游戏参数
        builder += game_arguments  # 拼接游戏参数

        builder.stdout = asyncio.subprocess.DEVNULL
        builder.stderr = asyncio.subprocess.DEVNULL

        builder.stdin = asyncio.subprocess.DEVNULL

        if show_args:  # 可选的展示启动参数列表（注意，是列表，不是 shell 参数）
            console.print(builder.args)

        ps = await builder.run()
        console.print(tr(r"进程 [dim]\[PID {}][/] 已启动，请等待", ps.pid))

        try:
            return_code = await ps.wait()
        except KeyboardInterrupt:
            with console.status(tr("正在停止")):
                ps.kill()
                await ps.wait()

            console.print(tr("游戏已退出"))
            raise typer.Abort()

        if return_code:
            # print((await ps.stdout.read()).decode())
            # print((await ps.stderr.read()).decode())

            console.print(tr("游戏发生错误 (退出代码 {})", return_code))
            console.print(Panel(
                Group(
                    f"[link=file:///{(ins.logs_dir / 'latest.log').absolute()}]{tr('查看游戏最后的输出')}[/link]",
                )
            ))
        else:
            console.print(tr("游戏已正常退出"))
