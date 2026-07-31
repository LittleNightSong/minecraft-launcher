import asyncio
import os
import re
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
from app.core.minecraft import VersionMetaModel, rules_matcher
from app.core.minecraft.api import MinecraftAPI
from app.core.minecraft.resources import InstanceDirectory
from app.core.models import FileInfo
from app.core.models.launch_context import LaunchContext, BasicJVMContext
from app.core.network import Session
from app.core.process_builder import ProcessBuilder
from app.interfaces.commandline import typer_app
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.methods import find_repository, status


# noinspection PyAttributeOutsideInit
class LaunchCommand(Command, app=typer_app):
    name = 'launch'

    async def check_all_files(self, ins: InstanceDirectory, meta: VersionMetaModel):
        files = []
        files.extend(
            self.repo.assets.indexes.read(meta.assets).iter_fileinfo(assets_dir=self.repo.assets)
        )
        files.extend(self.repo.libraries.get_library_files(
            matcher=rules_matcher,
            libraries=meta.libraries
        ))
        files.append(
            FileInfo.from_downloads_struct(
                downloads=meta.downloads.client,
                filename=ins.main_file
            )
        )

        return res_false_filter(
            await status(
                task=asyncio.gather(*[
                    self.file_validator.validate(file)
                    for file in files
                ]),
                content="校验文件中",
                console=console
            )
        )

    async def unzip_native_libraries(self, ins: InstanceDirectory, meta: VersionMetaModel):
        loop = asyncio.get_event_loop()
        required_natives = meta.get_unzip_required_libraries(rules_matcher)
        # console.print(required_natives)
        tasks = [
            loop.run_in_executor(
                self.pool,

                extract_to,
                self.repo.libraries.path / i.downloads.classifiers[
                    Template(i.natives[rules_matcher.os_name]).substitute(rules_matcher.env)
                ].path,
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
        :param quick_play: 快速启动目标
        :param show_args: 是否输出游戏启动参数
        :param show_uuid: 是否显示用户的 UUID
        :return:
        """
        ins: InstanceDirectory = self.repo.versions.instance(name)
        if not ins.is_valid():
            console.error(tr("指定的版本不存在"))
            raise typer.Abort()

        meta = ins.version_meta

        # 校验所有资源
        result = await self.check_all_files(ins, meta)
        if result:
            console.error(tr("版本文件存在问题，请使用 [green]install[/green] 修复后再启动"))
            raise typer.Abort()

        if username is None:
            username = console.prompt("输入游玩时使用的用户名：", abort=True)

        # 检查一下名字的长度
        if len(username) > 16:  # 1.20.3 起限制长度只能是 16 字符, 我们这里可能接触到快照版, 不好判断, 干脆不处理了...
            console.warning("您的用户名长度大于 16, 游玩 1.20.3 以上版本将无法进入游戏")

        # 再检测一下有没有不在官方给的允许字符中的字符
        if re.match(r'[^a-zA-Z0-9_]', username):
            console.warning("用户名包含特殊字符, 游玩 1.18 以上版本时将无法进入游戏")

        console.print()

        # 处理登录  # TODO: 支持正版登录和第三方登录
        match usertype:
            case 'offline':
                uuid = self.api.get_uuid_by_name_offline(username)
                token = 'FFFF'
                xuid = 'none'
                clientid = 'none'
            case _:
                console.error(f"不支持的用户类型 {usertype}")
                raise typer.Abort()

        console.print(f"登录成功 (模式 [yellow bold]{usertype}[/]), 您的用户名为 {username}")
        if show_uuid:
            console.print(tr("[dim]UUID={}[/dim]", uuid))

        # 拼接 classpath
        # # 首先找到所有的不是 natives 的 library 文件
        non_native_libraries = [i for i in ins.version_meta.libraries if not i.natives]
        classpath_list = {
            str(self.repo.libraries.path / lib.downloads.artifact.path)
            for lib in non_native_libraries
            if lib.downloads.artifact  # 这个比较迷惑，旧版有些 library 不提供 artifact
        }

        # 记得加上 Minecraft 主 jar
        classpath_list.add(str(ins.main_file))

        classpath_sep = ';' if os.name == 'nt' else ':'
        classpath = classpath_sep.join(classpath_list)

        ctx = LaunchContext(
            username=username,
            version_name=ins.version_meta.id,
            version_type='',
            game_dir=ins.path,
            assets_dir=self.repo.assets.path,
            assets_index_name=ins.version_meta.assets,

            uuid=uuid,
            token=token,
            clientid=clientid,
            xuid=xuid,

            natives_dir=ins.natives_dir,
            launcher_name='clcl',
            launcher_version=str(114514),

            classpath=classpath,

            classpath_sep=classpath_sep,
            libraries_directory=self.repo.libraries.path
        )

        if quick_play is not None:
            type_, value = quick_play.split(':', 1)
            match type_:
                case 'save':
                    ctx.quick_play_single_player = value
                case 'server':
                    ctx.quick_play_multi_player = value
                case 'realm':
                    ctx.quick_play_realms = value
                case _:
                    console.error(tr("不支持的快速启动目标类型：{}", type_))
                    raise typer.Abort()

        features = ctx.generate_features().to_dict()
        env = ctx.to_dict()

        memory_info = psutil.virtual_memory()
        available_memory = memory_info.available

        if memmax is None:
            allocator = MemoryAllocator()
            memmax = allocator.allocate(available_memory)  # 提前把 allocator 返回的字节数转换成字符串

            if memmax < 2097152:  # 16Mib
                console.error("可用内存太小, 无法分配所需的内存")
                raise typer.Abort()

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

        jvm_ctx = BasicJVMContext(
            mem_min=memmin or '16M', mem_max=memmax
        )

        pb = ProcessBuilder()
        pb |= ins.path  # 设置工作目录在版本文件夹中
        # 设置 java executable 位置
        # 找到一个最接近要求的 java
        # 首先获取所有适合的 Java (所有 major 版本大于版本要求的)
        suitable_javas: list[JavaRecord] = list(cfg.get_javas_forward(ins.version_meta.java_version.major_version))

        if not suitable_javas:
            console.error(tr("找不到适合的 Java 版本"))
            raise typer.Abort()

        # 排个序, 从小到大排
        suitable_javas.sort(key=lambda r: r.major)
        # 找第一个并设置为启动时使用的 java
        chosen_java = None

        for candy in suitable_javas:
            if os.path.exists(candy.path):
                chosen_java = candy
                break

        if chosen_java is None:
            console.error("本地无有效 Java")
            raise typer.Abort()

        pb <<= chosen_java.javaw_path()  # 设置 java executable

        console.print(tr(
            "已选择位于 [path]\"{}\"[/] 的 [yellow]java {}[/]", chosen_java.path, chosen_java.major),
            highlight=False
        )
        # console.tip(tr("Java 主版本: {}", chosen_java.major))

        jvm_arguments = meta.format_jvm_args(env, rules_matcher, features)  # 获取 jvm 参数
        # print(jvm_arguments)
        if not jvm_arguments:  # 如果没有返回 jvm 参数（游戏版本太低(1.13-)不支持）
            jvm_arguments = [
                f"-Dorg.lwjgl.librarypath={ins.natives_dir}",
                f"-Djava.library.path={ins.natives_dir}",
                '-cp', classpath,
            ]

            if chosen_java.major >= 17:
                jvm_arguments.append('--enable-native-access=ALL-UNNAMED')

            with console.status('解压本地库文件'):
                await self.unzip_native_libraries(ins, meta)

        # 获取 game 参数
        game_arguments = meta.format_game_args(env, rules_matcher, features)

        jvm_extension_arguments = [  # 暂无
        ]

        pb += jvm_extension_arguments  # 启动器给的参数优先级最小
        pb += jvm_arguments  # 随后是游戏给出的(虽然老版本中他也是启动器生成的)
        pb += jvm_ctx.to_args()  # 接下来是配置参数, 这个参数和其它参数基本不冲突
        pb += meta.main_class  # 放主类, 主类之后就是游戏参数
        pb += game_arguments  # 拼接游戏参数

        if show_args:
            console.print(pb.args)


        ps = await pb.run()
        console.print(tr(r"进程 \[PID {}] 已启动，请等待", ps.pid))

        try:
            return_code = await ps.wait()
        except KeyboardInterrupt:
            with console.status(tr("正在停止")):
                ps.kill()
                await ps.wait()

            console.print(tr("游戏已退出"))
            raise typer.Abort()

        if return_code:
            print((await ps.stdout.read()).decode())
            print((await ps.stderr.read()).decode())

            console.print(tr("游戏发生错误 (退出代码 {})", return_code))
            console.print(Panel(
                Group(
                    f"[link=file:///{(ins.logs_dir / 'latest.log').absolute()}]{tr('查看游戏最后的输出')}[/link]",
                )
            ))
        else:
            console.print(tr("游戏已正常退出"))
