import functools

import sys
sys.path.append('./src')

from app.core.pprofile import chronomia


chronomia.start()

import atexit
atexit.register(functools.partial(chronomia.save_report, 'performance_report.mpk'))

with chronomia("Application"):
    with chronomia("Setup"):
        from datetime import datetime

        import rich.traceback
        from loguru import logger


        with chronomia("Load Core"):
            import app.core.async_backend as lp
            from app.core.common import app_dirs
            from app.core.configs import cfg
            from app.core.i18n import tr
            from app.interfaces.commandline import typer_app
            from app.interfaces.commandline.base import console

        rich.traceback.install(show_locals=True, locals_max_depth=10000, locals_max_length=10000)

        with chronomia("Initialize logger"):
            logger.remove()
            logger.add(
                'logs/app.log',
                rotation='8 MB',
                retention='30 days',

                compression='zip'
            )

        with chronomia("Load Config"):
            cfg.set_path(app_dirs.user_config_dir)
            cfg.load()

        lp.set_event_loop()  # 不填参数, 默认创建高性能的 UVLoop

        import app.interfaces.commandline.commands  # type: ignore


        def main():
            logger.info(f"程序已启动 [{datetime.now()}]")
            try:
                typer_app()
            except Exception as e:
                logger.opt(exception=e).error("运行时发生错误")
                console.error(tr("发生未知错误，程序已退出（{}：{}）", e.__class__.__name__, e))

            finally:
                cfg.save()


    if __name__ == '__main__':
        with chronomia("Main"):
            main()

