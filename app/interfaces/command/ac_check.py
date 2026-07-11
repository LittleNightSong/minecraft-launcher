import typer

from app.core.common.concurrent_ import as_sync
from app.core.i18n import tr
from app.interfaces.command import typer_app
from app.interfaces.command.methods import find_repo
from app.interfaces.command.common import console


@typer_app.command()
@as_sync
def check(name, *, repo: str | None = typer.Option(None, '--repo', '-r')):
    repo = find_repo(repo, ask=False)
    if repo is None:
        console.print(f'[red]{tr("未指定储存库位置")}[/red]')