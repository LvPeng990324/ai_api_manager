import asyncio
from typing import Awaitable, Set

_running: Set[asyncio.Task] = set()


def run_in_background(coro: Awaitable[None]) -> None:
    task = asyncio.create_task(coro)
    _running.add(task)
    task.add_done_callback(_running.discard)


async def wait_background_tasks(timeout: float | None = 5.0) -> None:
    if not _running:
        return
    tasks = list(_running)
    if timeout is None:
        await asyncio.gather(*tasks, return_exceptions=True)
    else:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
