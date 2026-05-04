import os

import rich.traceback
from loguru import logger

# DO NOT REMOVE THESE
import app.interfaces.command.ac_install  # type: ignore
import app.interfaces.command.ac_list  # type: ignore
from app.interfaces.command import typer_app

# END

rich.traceback.install(show_locals=True, locals_max_depth=10000, locals_max_length=10000)

if level := os.environ.get('DEBUG', None):
    logger.enable(level)
else:
    logger.remove()

if __name__ == '__main__':
    typer_app()
