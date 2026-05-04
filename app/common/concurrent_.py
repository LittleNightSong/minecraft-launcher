try:
    import uvloop as loop_backend
except ImportError:
    import winloop as loop_backend

import asyncio
import functools
from collections.abc import Callable
from concurrent.futures.interpreter import InterpreterPoolExecutor
from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Coroutine, Any

thread_pool = ThreadPoolExecutor()
process_pool = ProcessPoolExecutor()
interpreter_pool = InterpreterPoolExecutor()


async def run_in_thread[T](func: Callable[..., T], *args) -> T:
    return await asyncio.get_running_loop().run_in_executor(thread_pool, func, *args)


async def run_in_process[T](func: Callable[..., T], *args) -> T:
    return await asyncio.get_running_loop().run_in_executor(process_pool, func, *args)


async def run_in_interpreter[T](func: Callable[..., T], *args) -> T:
    return await asyncio.get_running_loop().run_in_executor(interpreter_pool, func, *args)


def threaded[**P, T](func: Callable[P, T]) -> Callable[P, Coroutine[Any, Any, T]]:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await run_in_thread(lambda: func(*args, **kwargs))

    return wrapper


def processed[**P, T](func: Callable[P, T]) -> Callable[P, Coroutine[Any, Any, T]]:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await run_in_process(lambda: func(*args, **kwargs))

    return wrapper


def interpreted[**P, T](func: Callable[P, T]) -> Callable[P, Coroutine[Any, Any, T]]:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await run_in_interpreter(lambda: func(*args, **kwargs))

    return wrapper


def as_sync[**P, T](
        func: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, T]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return loop_backend.run(func(*args, **kwargs))

    return wrapper


def reset_max_threads(max_threads: int | None = None) -> None:
    global thread_pool
    thread_pool.shutdown(wait=True)
    thread_pool = ThreadPoolExecutor(max_workers=max_threads)


def reset_max_processes(max_threads: int | None = None) -> None:
    global process_pool
    process_pool.shutdown(wait=True)
    process_pool = ProcessPoolExecutor(max_workers=max_threads)


def reset_max_interpreters(max_threads: int | None = None) -> None:
    global interpreter_pool
    interpreter_pool.shutdown(wait=True)
    interpreter_pool = InterpreterPoolExecutor(max_workers=max_threads)
