import locale
from typing import Callable

import rich.console
import typer

from app.network import Session

locale.setlocale(locale.LC_ALL, '')

typer_app = typer.Typer(no_args_is_help=True)
console = rich.console.Console()
session = Session()


def assert_[**P](
        condition, exception_type: Callable[P, BaseException] = AssertionError, *args: P.args, **kwargs: P.kwargs
):
    if not condition:
        raise exception_type(*args, **kwargs)
