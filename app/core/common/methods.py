import functools
import os
import shutil
from string import Template
from typing import Callable

import msgspec


def as_async(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def read_model[T](
        file, type: type[T],
        decoder=None,
        default: T =...,
        default_factory: Callable[[], T] = ...
) -> T:
    try:
        with open(file, 'rb') as f:
            return (decoder or msgspec.json.decode)(f.read(), type=type)
    except (FileNotFoundError, PermissionError, msgspec.ValidationError, msgspec.DecodeError) as e:
        if default is not ...:
            return default
        elif default_factory is not ...:
            return default_factory()
        else:
            raise e


def write_model(file, obj, encoder=None):
    with open(file, 'wb') as f:
        f.write((encoder or msgspec.json.encode)(obj))


def read_object(file, decoder=None):
    with open(file, 'rb') as f:
        return (decoder or msgspec.json.decode)(f.read())


def write_object(file, obj, encoder=None):
    with open(file, 'wb') as f:
        f.write((encoder or msgspec.json.encode)(obj))


def xpath(obj, path):
    for part in path.split('/'):
        if not part:
            continue

        obj = obj[part]
    return obj


def dotpath(obj, path):
    # original_obj = obj
    # try:
    for part in path.split('.'):
        if not part:
            continue

        obj = obj[part]
    return obj


def listpath(obj, *path):
    for part in path:
        obj = obj[part]

    return obj


def format_args(args, kwargs):
    parts = [*map(repr, args), *[f"{k}={v!r}" for k, v in kwargs.items()]]
    return '(' + ', '.join(parts) + ')'


def trace(maybe_func=None, *, hide_return=False, hide_args=False):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                value = func(*args, **kwargs)
            finally:
                args_ = format_args(args, kwargs) if not hide_args else '...'
                return_value = repr(value if 'value' in locals() else '<Error>') if not hide_return else '<Not Trace>'

                print(f"TRACE {func.__name__}{args_} -> {return_value}")

            if 'value' in locals():
                return value
            return None

        return wrapper

    return decorator if maybe_func is None else decorator(maybe_func)


def hardlink_copy(src: str, dest: str):
    """硬链接复制函数"""
    os.link(src, dest)


def fastcopy(src: os.PathLike[str], dest: os.PathLike[str]):
    src = os.path.realpath(src)
    dest = os.path.realpath(dest)

    if not os.path.isdir(src):
        raise NotADirectoryError(src)

    # 选择复制函数
    if os.stat(src).st_dev != os.stat(dest).st_dev:
        copy_func = shutil.copy2  # 不同设备用完整复制
    else:
        copy_func = hardlink_copy  # 同一设备用硬链接

    # 使用 copytree 的 dirs_exist_ok (Python 3.8+)
    shutil.copytree(src, dest, copy_function=copy_func, dirs_exist_ok=True)


def template_fill(__tmpl, __mapping=None, **kwargs):
    if __mapping is None:
        __mapping = {}

    return Template(__tmpl).substitute(__mapping, **kwargs)
