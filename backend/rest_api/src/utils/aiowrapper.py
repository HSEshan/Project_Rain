import asyncio
import functools
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

pool = ThreadPoolExecutor(
    max_workers=os.cpu_count() or 1,
    thread_name_prefix="aio_thread",
)


def aio(fn: Callable[P, R]) -> Callable[P, Awaitable[R]]:
    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(pool, functools.partial(fn, *args, **kwargs))

    return wrapper
