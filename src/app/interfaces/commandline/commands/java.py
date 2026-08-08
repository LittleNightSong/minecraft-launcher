import rich.box
import rich.markup
import rich.table
from rich.text import Text

from app.core.configs import JavaRecord, cfg
from app.core.i18n.translator import tr, trs
from app.core.java.detector import detect_java_from_java_home, detect_java_from_path_env, detect_java_from_programs, \
    get_simple_type
from app.interfaces.commandline.base.command_base import CommandGroup
from app.interfaces.commandline.base.console_extensions import console


def _show_javas(javas_list):
    table = rich.table.Table(
        *trs("主版本", "类型", "路径"),
        expand=True,
        box=rich.box.ROUNDED,
        header_style="bold magenta",
    )

    for java in javas_list:
        path_text = Text.from_markup(
            f'[green][link=file:///{java.path}]{rich.markup.escape(java.path)}[/][/]    ', overflow='ellipsis'
        )
        path_text.no_wrap = True
        table.add_row(
            Text.from_markup(f'[repr.number]{java.major}[/]'),
            Text.from_markup(f'[yellow]{get_simple_type(java.type)}[/]'),
            path_text
        )

    console.print(table)


class JavaCommands(CommandGroup):
    name = 'java'
    commands = ['scan', 'show']

    async def init(self):
        ...

    async def scan(self, paths: list[str] | None = None):
        if paths is None:
            java1 = await detect_java_from_java_home()
            java2 = [i async for i in detect_java_from_path_env()]
            java3 = [i async for i in detect_java_from_programs()]

            # console.print(java1, java2, java3)

            # 全部转换成 JavaRecord
            javas: set[JavaRecord] = set()

            if java1:
                javas.add(JavaRecord.new(*java1))

            for item in java2:
                javas.add(JavaRecord.new(*item))

            for item in java3:
                javas.add(JavaRecord.new(*item))

            if not javas:
                console.print("无结果")
                return

            # 先保存要紧
            [cfg.add_java_record(rec) for rec in javas]

            # 输出发现了哪些 java

            console.print(tr("已找到 {} 个 Java 入口点", len(javas)), end='\n\n')

            _show_javas(sorted(javas, key=lambda r: r.major))

    async def show(self):
        javas = sorted(cfg.get_all_javas(), key=lambda r: r.major)

        console.print(tr("本地共有 {} 个 Java 入口点", len(javas)), end='\n\n')

        _show_javas(javas)
