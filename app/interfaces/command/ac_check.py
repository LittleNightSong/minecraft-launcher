import typer

from app.common.concurrent_ import as_sync
from app.interfaces.command import typer_app
from app.interfaces.command.ac_install import find_repo


@typer_app.command()
@as_sync
def check(name, *, repo: str | None = typer.Option(None, '--repo', '-r')):
    repo = find_repo(repo, ask=False)