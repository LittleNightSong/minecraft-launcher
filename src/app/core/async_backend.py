import asyncio

try:
    import uvloop as loop_backend
except ImportError:
    try:
        import winloop as loop_backend
    except ImportError:
        import asyncio as loop_backend


def run(coro):
    return loop_backend.run(coro)


def new_event_loop() -> asyncio.AbstractEventLoop:
    return loop_backend.new_event_loop()


def get_running_loop() -> asyncio.AbstractEventLoop:
    return asyncio.get_running_loop()


def set_event_loop(loop: asyncio.AbstractEventLoop | None = None) -> None:
    asyncio.set_event_loop(loop or new_event_loop())


def get_event_loop() -> asyncio.AbstractEventLoop:
    return asyncio.get_event_loop()


def run_until_complete(coro):
    loop = get_event_loop()
    return loop.run_until_complete(coro)
