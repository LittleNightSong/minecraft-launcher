import os
import zipfile
from datetime import datetime
from pathlib import Path

import msgspec
import typer

from app.core.i18n import tr
from app.interfaces.commandline.base.command_base import Command
from app.interfaces.commandline.base.console_extensions import console
from app.interfaces.commandline.base.methods import find_repository


def safe_write(w: zipfile.ZipFile, file):
    if os.path.isfile(file):
        w.write(file, os.path.basename(file))


def safe_rwrite(w: zipfile.ZipFile, dir):
    if os.path.isdir(dir):
        dirname = os.path.basename(dir)
        for dirpath, dirnames, filenames in Path(dir).walk():
            parent = os.path.join(dirname, dirpath.relative_to(dir))
            w.mkdir(parent)
            for f in filenames:
                final_path = os.path.join(parent, f)
                console.print({
                    'dir': dir,
                    'current_dir': dirpath,
                    'arc_path': final_path,
                    'parent_dir': parent,
                })
                w.write(os.path.join(dirpath, f), final_path)


# noinspection PyAttributeOutsideInit
class BackupCommand(Command):
    name = 'backup'

    async def init(self, repo, name, output, **kwargs):
        self.repo = find_repository(repo, ask=False, raise_for_unset=True)
        self.instance = self.repo.versions.instance(name)
        self.output = Path(output or f'{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip')

    async def main(
            self,
            name: str,*,
            output: Path | None = typer.Option(None, '-o', '--output'),
            yes: bool = False,

            repo: str | None = None,

            saves: bool = False, mods: bool = False,
            configs: bool = True, rcpacks: bool = False,
            srpacks: bool = False

    ):
        output = self.output

        if not output.parent.is_dir():
            console.confirm(
                tr("路径 {} 不存在, 是否创建它", output.parent),
                skip=yes, abort=True
            )
            os.makedirs(output.parent, exist_ok=True)

        if os.path.isfile(output):
            console.confirm(
                tr("文件 {} 已存在, 是否覆盖?", output),
                skip=yes, abort=True
            )

        with zipfile.ZipFile(output, 'w') as z:
            if saves:
                safe_rwrite(z, self.instance.saves_dir)

            if mods:
                safe_rwrite(z, self.instance.mods_dir)

            if configs:
                safe_rwrite(z, self.instance / 'config')

            if rcpacks:
                safe_rwrite(z, self.instance.resourcepacks_dir)

            if srpacks:
                safe_rwrite(z, self.instance.shaderpacks_dir)


            # 随后添加元数据
            version_meta = self.instance.version_meta
            with z.open('metadata.json', 'w') as f:
                f.write(msgspec.json.encode())

        console.print(tr("导出成功, 文件已保存至 [link={0}]{1}[/]", f"file:///{output.absolute()}", output.absolute()))

    async def cleanup(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            os.unlink(self.output)
