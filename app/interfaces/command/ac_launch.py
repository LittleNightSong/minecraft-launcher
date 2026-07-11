import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from string import Template
from typing import Literal
from uuid import uuid4

import typer

from app.core.common import FileInfo
from app.core.common.file_validator import res_false_filter, FileValidator
from app.core.common.zzipfile import extract_to
from app.core.i18n import tr
from app.core.java.process_builder import ProcessBuilder
from app.core.minecraft import VersionMetaModel
from app.core.minecraft.launch_context import LaunchContext, BasicJVMContext
from app.core.resources.base import rules_matcher
from app.core.resources.instance import InstanceDirectory
from app.interfaces.command import typer_app
from app.interfaces.command.command import Command
from app.interfaces.command.common import console
from app.interfaces.command.methods import find_repo, status


# noinspection PyAttributeOutsideInit
class LaunchCommand(Command, app=typer_app):
    name = 'launch'

    async def check_all_files(self, ins: InstanceDirectory, meta: VersionMetaModel):
        files = []
        files.extend([
            FileInfo(
                filename=self.repo.assets / hash,
                hash=hash,
                size=size
            )
            for _, hash, size in self.repo.assets.indexes.read(meta.assets).iter_object()
        ])
        files.extend([
            FileInfo.from_downloads_struct(
                downloads=downloads,
                filename=self.repo.libraries.path / downloads.path
            )
            for lib in meta.libraries
            for downloads in lib.collect_files(rules_matcher)
        ])
        files.append(
            FileInfo.from_downloads_struct(
                downloads=meta.downloads.client,
                filename=ins.main_file
            )
        )

        return res_false_filter(
            await status(
                asyncio.gather(*[
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
                    Template(i.natives[rules_matcher.os_name]).substitute(rules_matcher.get_env())
                ].path,
                ins.natives_dir
            )
            for i in required_natives
        ]
        await asyncio.gather(*tasks)

    async def init(self, repo, *args, **kwargs):
        self.repo = find_repo(repo, raise_for_unset=True)
        self.pool = ThreadPoolExecutor(max_workers=32)
        self.file_validator = FileValidator(executor=self.pool)

    async def main(
            self,
            name: str,
            username: str, usertype: Literal['online', 'offline', 'littleskin'] = 'offline',
            repo: Path | None = None,  # 这个参数在 init 中被处理
            memmax: str | None = None,
            memmin: str | None = None,
    ):
        ins = self.repo.versions.instance(name)
        if not ins.is_vaild():
            console.error(tr("指定的版本不存在"))
            raise typer.Abort()

        meta = ins.version_meta

        # 校验所有资源
        result = await self.check_all_files(ins, meta)
        if result:
            console.error(tr("版本文件存在问题，请使用 [green]install[/green] 修复后再启动"))
            # console.print(result)
            raise typer.Abort()

        # 处理登录  # TODO: 支持正版登录和第三方登录
        if usertype != 'offline':
            console.error(f"不支持的用户类型 {usertype}")
            raise typer.Abort()

        else:
            uuid = uuid4()
            token = 'None Token'
            xuid = 'none'
            clientid = 'none'

        # 拼接 classpath
        # # 首先找到所有的不是 natives 的 library 文件
        non_native_libraries = [i for i in ins.version_meta.libraries]
        classpath_list = [
            str(self.repo.libraries.path / lib.downloads.artifact.path)
            for lib in non_native_libraries
            if lib.downloads.artifact  # 这个比较迷惑，旧版有些 library 不提供 artifact
        ]

        # 记得加上 Minecraft 主 jar
        classpath_list.append(str(ins.main_file))

        classpath = ';'.join(classpath_list) if os.name == 'nt' else ':'.join(classpath_list)

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

            classpath=classpath
        )

        jvm_ctx = BasicJVMContext(
            memmin=memmin or '1024M', memmax=memmax or '2048M'
        )

        env = ctx.to_dict()

        pb = ProcessBuilder()
        # 设置 java executable 位置
        pb << r'D:\Program Files\openjdk-26_windows-x64_bin\jdk-26\bin\javaw.exe'  # TODO: 自动检测 java 和保存历史 java 路径

        jvm_arguments = meta.format_jvm_args(env, rules_matcher)  # 获取 jvm 参数
        # print(jvm_arguments)
        if not jvm_arguments:  # 如果没有返回 jvm 参数（游戏版本太低(1.13-)不支持）
            # # TODO
            # console.error("暂不支持启动此版本")
            # raise typer.Abort()
            jvm_arguments = [
                f"-Dorg.lwjgl.librarypath={ins.natives_dir}",
                f"-Djava.library.path={ins.natives_dir}",
                '-cp', classpath,
            ]

            await self.unzip_native_libraries(ins, meta)

        # 获取 game 参数
        game_arguments = meta.format_game_args(env, rules_matcher)

        pb += jvm_arguments
        pb += jvm_ctx.to_args()
        pb += meta.main_class
        pb += game_arguments

        console.print(pb.args)

        # with console.status(tr("解压库文件")):
        #     await self.unzip_natives(ins, meta)

        ps = await pb.run()

        if return_code := await ps.wait():
            print((await ps.stdout.read()).decode())
            print((await ps.stderr.read()).decode())
            console.print(f"游戏发生错误 (退出代码 {return_code})")
        else:
            pass
