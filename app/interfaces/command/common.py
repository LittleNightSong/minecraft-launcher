import locale
from typing import Callable

import rich.console
import rich.markup
import typer

from app.core.network import Session

locale.setlocale(locale.LC_ALL, '')


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


typer_app = typer.Typer(
    no_args_is_help=True,
    # async_runner=async_run
)

console = MyConsole()
session = Session()


def assert_[**P](
        condition, exception_type: Callable[P, BaseException] = AssertionError, *args: P.args, **kwargs: P.kwargs
):
    if not condition:
        raise exception_type(*args, **kwargs)
