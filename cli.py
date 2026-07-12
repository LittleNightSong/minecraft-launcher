import os
from datetime import datetime

import rich.traceback
from loguru import logger

# DO NOT REMOVE THESE
import app.interfaces.command.ac_install  # type: ignore
import app.interfaces.command.ac_launch  # type: ignore
import app.interfaces.command.ac_list  # type: ignore
from app.interfaces.command import typer_app

# from app.interfaces.command.common import console

# END

# console.print("PID:", os.getpid())

rich.traceback.install(show_locals=True, locals_max_depth=10000, locals_max_length=10000)
logger.remove()

logger.add(
    'logs/app.log',
    rotation='1 day',
    compression='zip',
)

if __name__ == '__main__':
    # logger.log('', '\n\n\n')
    logger.info(f"程序已启动 [{datetime.now()}]")
    typer_app()
