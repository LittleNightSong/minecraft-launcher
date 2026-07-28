from datetime import datetime

import rich.traceback
from loguru import logger

from app.core.common import app_dirs
from app.core.configs import cfg
from app.interfaces.commandline import typer_app

import app.core.async_backend as lp

rich.traceback.install(show_locals=True, locals_max_depth=10000, locals_max_length=10000)

logger.remove()
logger.add(
    'logs/app.log',
    rotation='8 MB',
    retention='30 days',

    compression='zip'
)

cfg.set_path(app_dirs.user_config_dir)
cfg.load()

lp.set_event_loop()  # 不设置, 默认创建高性能的 UVLoop

import app.interfaces.commandline.commands  # type: ignore

if __name__ == '__main__':
    logger.info(f"程序已启动 [{datetime.now()}]")
    try:
        typer_app()
    except Exception as e:
        logger.opt(exception=e)
        raise e

    finally:
        cfg.save()
