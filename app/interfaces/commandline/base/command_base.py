import functools
import inspect
from typing import ClassVar, Callable, Iterable, Coroutine

import docutils.parsers
import typer
from docutils.core import publish_doctree
from docutils.nodes import paragraph
from loguru import logger
from typer import Typer

import app.core.async_backend as lp
from app.core.common.errors import ExceptionForUser
from .console_extensions import console

typer_app = typer.Typer(
    no_args_is_help=True,
    # async_runner=async_run
)


def rewrite_func_signature(signature: inspect.Signature, field_docs: dict[str, str]):
    raw_params = tuple(signature.parameters.values())[1:]  # 记得删除 self 参数
    params = []
    for p in raw_params:
        key = f'param {p.name}'
        if key in field_docs:
            doc = field_docs[key]
            default_value = p.default
            if isinstance(default_value, typer.models.ArgumentInfo | typer.models.OptionInfo):
                if default_value.help is not None:
                    logger.warning("该参数已提供 typer 风格的帮助字符串，文档字符串将不会覆盖原有帮助信息")
                else:
                    default_value.help = doc
            elif default_value is not p.empty:
                if p.kind in {p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD}:
                    info = typer.Argument(default_value, help=doc)
                elif p.kind is p.KEYWORD_ONLY:
                    info = typer.Option(default_value, help=doc)
                else:
                    raise NotImplementedError()

                p = p.replace(default=info)
            else:
                if p.kind in {p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD}:
                    info = typer.Argument(help=doc)
                elif p.kind is p.KEYWORD_ONLY:
                    info = typer.Option(help=doc)
                else:
                    raise NotImplementedError()

                p = p.replace(default=info)

        params.append(p)

    return signature.replace(parameters=params)


def process_func_doc(docstring):
    """
    处理函数文档
    分析函数文档，分离和整合自然段和 REST 标记部分，并返回

    :param docstring:
    :return: 一个三元组 (<自然段落字符串（已整理>, <参数文档字典>, <特殊标注字典>)
    """
    if not docstring:
        return "", {}

    try:
        tree = publish_doctree(docstring)
    except Exception as exc:
        # logger.opt(exception=exc).error(str(exc))
        return "", {}

    paragraphs = []
    fields = {}

    for node in tree.children:
        # print(node)
        if isinstance(node, docutils.nodes.paragraph):
            text = node.astext()
            if t := text.strip():
                paragraphs.append(t)

        elif isinstance(node, docutils.nodes.field_list):
            for node in node.children:
                name_nodes = list(node.findall(condition=docutils.nodes.field_name))

                if name_nodes:
                    filed_name = name_nodes[0].astext().strip()
                    body_nodes = list(node.findall(condition=docutils.nodes.field_body))

                    if body_nodes:
                        field_value = body_nodes[0].astext().strip()
                        fields[filed_name] = field_value

    natural_text = '\n\n'.join(paragraphs)

    return natural_text, fields


def get_init_args(cls, fn_name='init'):
    fn = getattr(cls, fn_name, None)
    if fn is not None:
        return tuple(inspect.signature(fn).parameters.keys())[1:]
    else:
        return ()


async def call_init(cls, self, kwargs, init_args: Iterable[str], fn_name='init'):
    if (fn := getattr(cls, fn_name, None)) is not None:
        await fn(self, **{
            k: kwargs[k]
            for k in init_args
        })


class Command:
    context: typer.Context

    name: ClassVar[str]
    __typer_run__: ClassVar[Callable]

    init: ClassVar[Callable]
    main: ClassVar[Callable]

    async def cleanup(self, exc_type, exc_val, exc_tb):
        ...

    def __init_subclass__(cls, app=typer_app, **kwargs):
        super().__init_subclass__(**kwargs)

        main = cls.main

        # 提取 init 函数的参数
        init_vars = get_init_args(cls)

        @functools.wraps(main)
        async def main_wrapper(**kwargs):
            self = cls()
            self.context = typer.main.get_current_context()
            async with self:
                try:
                    await call_init(cls, self, kwargs, init_vars)
                    return await main(self, **kwargs)
                except ExceptionForUser as rfu_exc:
                    console.error(str(rfu_exc))

        def run_main(**kwargs):
            return lp.run(main_wrapper(**kwargs))

        natural_doc, fields = process_func_doc(main.__doc__)

        cls.__main_wrapper__ = main_wrapper

        run_main.__signature__ = rewrite_func_signature(inspect.signature(main), fields)
        run_main.__name__ = cls.name
        run_main.__doc__ = natural_doc

        cls.__typer_run__ = run_main
        cls.__typer__ = Typer(no_args_is_help=True)
        cls.__typer__.command()(cls.__typer_run__)

        app.add_typer(cls.__typer__)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.cleanup(exc_type, exc_val, exc_tb)

    @classmethod
    def run_directly_unsafe(cls, **kwargs):
        command = typer.main.get_command(cls.__typer__)
        command.callback(**kwargs)

    @classmethod
    def run(cls, *argv: str):
        cls.__typer__(argv)

    @classmethod
    def call(cls, **kwargs) -> Coroutine:
        args = {
            k: (
                kwargs[k]
                if k in kwargs
                else (
                    v.default.default
                    if isinstance(v.default, typer.models.OptionInfo | typer.models.ArgumentInfo)
                    else
                    v.default
                )
            )

            for k, v in inspect.signature(cls.__typer_run__).parameters.items()
        }

        # print(args)

        return cls.__main_wrapper__(**args)


# class _Unset:
#     _instance = None
#
#     def __new__(cls, *args, **kwargs):
#         if cls._instance is None:
#             cls._instance = super().__new__(cls)
#
#         return cls._instance
#
#     def __str__(self):
#         return "UNSET"
#
#     def __repr__(self):
#         return "<UNSET object>"
#
#
# UNSET = _Unset()


def command(*, name):
    def decorator(fn):
        fn.__command_name__ = name
        return fn

    return decorator


class CommandGroup:
    # UNSET = UNSET

    name: ClassVar[str] = None
    commands: ClassVar[list[str]] = []

    invoked_subcommand: str | None

    init: ClassVar[Callable]

    async def cleanup(self, exc_type, exc_val, exc_tb):
        ...

    def __init_subclass__(cls, app=typer_app, **kwargs):
        sub_app = typer.Typer(name=cls.name, no_args_is_help=True)

        fns = [
            getattr(cls, name) for name in cls.commands
        ]

        init_vars = get_init_args(cls)

        def create_run_wrapper(name, fn):
            async def main_wrapper(**kwargs):
                self = cls()
                self.invoked_subcommand = name
                async with self:
                    await call_init(cls, self, kwargs, init_vars)
                    await fn(self, **kwargs)

            @functools.wraps(fn)
            def run_wrapper(**kwargs):
                return lp.run(main_wrapper(**kwargs))

            natural_doc, fields = process_func_doc(fn.__doc__)

            run_wrapper.__signature__ = rewrite_func_signature(inspect.signature(fn), fields)
            run_wrapper.__doc__ = natural_doc

            return run_wrapper

        for fn in fns:
            name = str(getattr(fn, '__command_name__', fn.__name__))
            sub_app.command(name=name)(create_run_wrapper(name, fn))

        cls.__typer__ = sub_app

        if app is not None:
            app.add_typer(cls.__typer__)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.cleanup(exc_type, exc_val, exc_tb)


def invoke(cmd: Command | CommandGroup, *args):
    return cmd.__typer__(*args)

# def param_decls(**kwargs: Iterable[str]):
#     def decorator(fn):
#         fn.__param_decls__ = kwargs
#         return fn
#
#     return decorator
