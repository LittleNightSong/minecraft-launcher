import locale
from typing import Callable

import rich.console
import typer

from app.network import Session

locale.setlocale(locale.LC_ALL, '')


class MyConsole(rich.console.Console):
    def note(self, *values):
        self.print(f"[green]NOTE:[/green]", *values)

    def error(self, *values):
        self.print(f"[red bold]Error:[/red bold]", *values)

    def warning(self, *values):
        self.print(f"[yellow bold]WARNING:[/yellow bold]", *values)


typer_app = typer.Typer(no_args_is_help=True)
console = MyConsole()
session = Session()


def assert_[**P](
        condition, exception_type: Callable[P, BaseException] = AssertionError, *args: P.args, **kwargs: P.kwargs
):
    if not condition:
        raise exception_type(*args, **kwargs)
