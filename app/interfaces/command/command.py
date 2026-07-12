import inspect
from typing import overload, ClassVar, Callable

import typer
from typer import Typer

from app.core.common.concurrent_ import async_run
from app.core.common.errors import ExceptionForUser
from app.interfaces.command.common import console


def process_func_signature(signature):
    return signature.replace(
        parameters=[
            v for v in signature.parameters.values()
            if v.name != 'self'
        ]
        #            + [inspect.Parameter(
        #     'ctx', kind=inspect.Parameter.KEYWORD_ONLY, annotation=typer.Context
        # )]  # 注入一个 ctx 参数
    )



class Command:
    name = None

    run: ClassVar[Callable]

    async def init(self, *args, **kwargs):
        ...

    main: ClassVar[Callable]

    async def cleanup(self, exc_type, exc_val, exc_tb):
        ...

    def __init_subclass__(cls, *, app: Typer, **kwargs):
        super().__init_subclass__(**kwargs)

        cls.app = app

        main = cls.main

        # @wraps(main)
        async def main_wrapper(**kwargs):
            self = cls()
            async with self:
                try:
                    await self.init(**kwargs)
                    return await main(self, **kwargs)
                except ExceptionForUser as rfu_exc:
                    console.error(str(rfu_exc))

        def run_main(**kwargs):
            return async_run(main_wrapper(**kwargs))

        run_main.__signature__ = process_func_signature(inspect.signature(main))

        cls.run = run_main

        if kwargs.get("auto_register", True):
            cls.register()

    @classmethod
    @overload
    def register(cls):
        ...

    @classmethod
    @overload
    def register(cls, app: Typer):
        ...

    @classmethod
    def register(cls, app: Typer | None = None):
        if app is None:
            app = cls.app

        app.command(name=cls.name)(cls.run)

    async def __aenter__(self):
        return

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.cleanup(exc_type, exc_val, exc_tb)
