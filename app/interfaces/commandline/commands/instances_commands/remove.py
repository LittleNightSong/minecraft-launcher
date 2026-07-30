import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor

import typer
from tqdm.asyncio import tqdm

from app.core.i18n import tr
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.methods import find_repository, make_multi_shower


# noinspection PyAttributeOutsideInit
class RemoveCommand(Command):
    name = 'remove'

    async def init(self, repo_path):
        self.minecraft = find_repository(repo_path, abort=True)
        self.loop = asyncio.get_event_loop()

    async def main(
            self,
            names: list[str],
            *,
            repo_path: str | None = typer.Option(None, '-r', '--repo'),
            max_threads: int = typer.Option(4, '-t', '--max-threads'),
            yes: bool = typer.Option(False, '-y', '--yes'),
    ):
        instances = self.minecraft.manifest.select(names)
        # 找出可能的无效的版本
        invaild_instances = [i._name for i in instances if not i.is_valid()]
        if invaild_instances:
            console.print(make_multi_shower(
                values=invaild_instances,
                title=tr("无效的实例"),
                style='red',
                border_style='red'
            ))
            raise typer.Abort()

        del invaild_instances

        console.confirm(tr("即将删除选中版本的所有数据，包括保存的存档、截图、设置，是否继续？"), skip=yes, abort=True)

        # 这时已经确认了
        self.thread_pool = ThreadPoolExecutor(max_workers=max_threads)

        with console.no_interrupt():
            await tqdm.gather(*[
                self.loop.run_in_executor(self.thread_pool, shutil.rmtree, i.path)
                for i in instances
            ])
