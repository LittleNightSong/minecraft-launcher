from pathlib import Path

from app.common.concurrent_ import as_sync
from app.interfaces.command import typer_app
from app.interfaces.command.ac_install import find_repo


@typer_app.command()
@as_sync
async def launch(
        name: str,
        repo: Path | None = None
):
    minecraft = find_repo(repo)
