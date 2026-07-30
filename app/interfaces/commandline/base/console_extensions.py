import codecs
import locale
import sys
from contextlib import contextmanager
from typing import Callable, Any, Iterable

import readchar
import rich.console
import rich.live
import rich.markup
import rich.table
import rich.text
# import rich.
import typer
from loguru import logger
from rich.control import Control
from rich.segment import ControlType

from app.core.i18n import tr
from app.core.network import Session
from app.interfaces.commandline.themes.loader import get_theme

locale.setlocale(locale.LC_ALL, '')

yes_no_mapping = {
    True: "yes",
    False: "no"
}


def _readchar_unix():
    import termios, tty
    stdin = sys.stdin

    fd = stdin.fileno()

    old_settings = termios.tcgetattr(fd)
    decoder = codecs.getincrementaldecoder('utf-8')()

    try:
        tty.setraw(fd)
        while True:
            ch = stdin.read(1)

            if not ch:  # EOF
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                return None

            char = decoder.decode(ch)
            if char:
                return char
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _readchar_windows():
    """
    Read a single character from stdin on Windows (without msvcrt).
    Returns a single Unicode string, or None on EOF (Ctrl+Z).
    Special keys like arrows may return a two‑character sequence
    ('\x00' or '\xe0' + keycode) across multiple calls.
    """
    import ctypes
    from ctypes import wintypes

    # Constants for console mode
    STD_INPUT_HANDLE = -10
    ENABLE_LINE_INPUT = 0x0002
    ENABLE_ECHO_INPUT = 0x0004
    ENABLE_PROCESSED_INPUT = 0x0001

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    # Get handle to the console's input buffer
    handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())

    # Save current console mode
    old_mode = wintypes.DWORD()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(old_mode)):
        raise ctypes.WinError(ctypes.get_last_error())

    # Set new mode: turn off line input and echo; keep processed input (so Ctrl+C still works)
    new_mode = old_mode.value & ~(ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT)
    new_mode |= ENABLE_PROCESSED_INPUT
    if not kernel32.SetConsoleMode(handle, new_mode):
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        while True:
            buf = ctypes.create_unicode_buffer(1)
            nread = wintypes.DWORD()
            # ReadConsoleW reads wide characters directly (Unicode)
            if not kernel32.ReadConsoleW(handle, buf, 1, ctypes.byref(nread), None):
                raise ctypes.WinError(ctypes.get_last_error())

            if nread.value == 0:  # No character read → treat as EOF
                return None

            ch = buf.value
            if ch == '\x1a':  # Ctrl+Z is the traditional Windows EOF marker
                return None

            # For normal printable characters and the first half of a special key,
            # simply return it. The next call will give the second half if applicable.
            return ch
    finally:
        # Restore the original console mode
        kernel32.SetConsoleMode(handle, old_mode)


class _MenuItem:
    def __init__(self, pre, post, key, selected: bool = False):
        self.text_pre_selected = pre
        self.text_post_selected = post
        self.key = key
        self.selected = selected

    @property
    def text(self):
        return (
            rich.text.Text.from_markup(self.text_pre_selected)) \
            if not self.selected else (
            rich.text.Text.from_markup(self.text_post_selected)
        )

    def __rich_console__(self, *args, **kwargs):
        return self.text.__rich_console__(*args, **kwargs)

    def __rich_measure__(self, *args, **kwargs):
        return self.text.__rich_measure__(*args, **kwargs)


class MyConsole(rich.console.Console):
    level = 2

    def error(self, *values):  # level=3
        if self.level > 3:
            return

        self.print(f"[red bold]Error:[/red bold]", *values)

    def warning(self, *values):  # level=2
        if self.level > 2:
            return

        self.print(f"[yellow bold]WARNING:[/yellow bold]", *values)

    def note(self, *values):  # level=1
        if self.level > 1:
            return

        self.print(f"[green]NOTE:[/green]", *values)

    def debug(self, *values):  # level=0
        if self.level > 0:
            return

        self.print(f"[blue]DEBUG:[/blue]", *values)

    def tip(self, value):
        self.print(f"[aim]{value}[/aim]")

    def confirm(self, prompt, skip=False, abort=False, default=True):
        if skip:
            return True

        with rich.live.Live(
                fr"{prompt} [dim]\[y/n] > [/dim][bright_cyan]{yes_no_mapping[default]}[/bright_cyan]",
                auto_refresh=False, console=self
        ) as live:
            try:
                while True:
                    key = readchar.readkey()

                    if isinstance(key, str):
                        key = key.lower()

                    if key == 'y':
                        live.update(fr"[bold]{prompt}[/bold] [dim]·[/dim] [bright_cyan]yes[/bright_cyan]")
                        return True

                    elif key == 'n':
                        live.update(fr"[bold]{prompt}[/bold] [dim]·[/dim] [bright_cyan]no[/bright_cyan]")

                        if abort:
                            raise typer.Abort()

                        return False

                    elif key == readchar.key.ENTER:
                        if abort and not default:
                            raise typer.Abort()

                        return default

                    elif key == readchar.key.ESC:
                        raise typer.Abort()


            except KeyboardInterrupt:
                raise typer.Abort()

    def menu(self, prompt, choices: Iterable[tuple[Any, Any | None, Any]]):
        if not choices:
            raise ValueError()
        # Choices: list[(text_pre, text_post | auto_generate, key)]
        # 首先构建一个 Table，用于展示选项
        table = rich.table.Table('A', 'B', 'C', title=prompt, box=None, show_header=False)

        table_list = []
        for i, (text_post, text_pre, key) in enumerate(choices):
            table_list.append((
                _MenuItem('', '[user-choice]❯[/]', None),
                _MenuItem(f'[dim]{i+1}[/]', f'[bold]{i+1}[/]', None),
                _MenuItem(text_pre or f'[dim]{text_post}[/dim]', text_post, key, i == 0)
            ))

        for item in table_list:
            table.add_row(*item)

        selected_index = 0

        def set_selected(index):
            nonlocal selected_index

            if index < 0:
                index += len(table_list)

            if not (0 <= index < len(table_list)):
                return

            table_list[selected_index][0].selected = False
            table_list[selected_index][1].selected = False
            table_list[selected_index][2].selected = False

            selected_index = index

            table_list[selected_index][0].selected = True
            table_list[selected_index][1].selected = True
            table_list[selected_index][2].selected = True

        set_selected(0)

        # self.print(table)

        with rich.live.Live(console=self, auto_refresh=False) as live:
            while True:
                # console.print("当前", selected_index)
                live.update(table)
                live.refresh()

                key = readchar.readkey()

                if key == readchar.key.ENTER:
                    return table_list[selected_index][2].key
                elif key == readchar.key.ESC:
                    return None
                elif key == readchar.key.UP or key == readchar.key.LEFT:
                    set_selected(selected_index -1)
                elif key == readchar.key.DOWN or key == readchar.key.RIGHT:
                    set_selected(selected_index + 1)
                elif key.isdigit():
                    i = int(key) - 1
                    if 0 <= i < len(table_list):
                        set_selected(i)
                else:
                    pass

    def prompt(
            self,
            prompt,
            abort: bool = False,
            validator: Callable[[str], tuple[bool, Any] | None] | None = None,
            suffix=' '
    ):
        # TODO: 支持 placeholder
        # 这里需要一些魔法了
        cnt = 0

        def show_prompt():
            self.print(f"[dim] > [/dim][bold]{prompt}[/bold]{suffix}", end='')

        def show_error(reason=None):
            nonlocal cnt
            cnt += 1
            reason = reason or tr("不合法的输入")
            move_up()
            clear_line()
            if cnt > 1:
                self.print(f"❌  ×[red]{cnt}[/red] [red]{reason}[/red]", end='')
            else:
                self.print(f"❌  [red]{reason}[/red]", end='')

        def show_success(data):
            move_up()
            clear_line()
            self.print(f"✅ [bold]{prompt}[/bold]{suffix}[reset][user-choice]{rich.markup.escape(data)}[/][/reset]",
                       end='')

        def clear_line():
            self.control(Control(
                (ControlType.ERASE_IN_LINE, 2)
            ))

        def move_up(length=1):
            self.control(Control.move(y=-length))

        # move_up(1)
        while True:
            show_prompt()
            try:
                data = input()
            except KeyboardInterrupt:
                if abort:
                    raise typer.Abort()
                else:
                    console.print()
                    return None

            if not data:
                move_up()
                continue

            if validator is None:
                # 擦除内容
                show_success(data)
                self.print()  # 换行
                return data

            try:
                result = validator(data)
                if result is None:
                    show_error()
                    continue

                ok, value = result
                if ok:
                    show_success(str(value))
                    self.print()
                    return value
                else:
                    show_error(value)
            except Exception as e:
                logger.opt(exception=e).warning("调用验证器 {} 时发生错误")

                show_error()

    @contextmanager
    def no_interrupt(self):
        import signal
        the_old = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            yield None
        finally:
            signal.signal(signal.SIGINT, the_old)


console = MyConsole(theme=get_theme())
session = Session()


class Link:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url

    def __str__(self):
        return f'[link={self.url}]{self.text}[/link]'
