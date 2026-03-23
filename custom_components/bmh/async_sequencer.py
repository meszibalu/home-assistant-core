"""Async sequencer is a utility class which prevents overlapping async tasks.

When a new task is started it is guaranteed the task does not run concurrently
with the previous task. The previous task is awaited before starting the new
task.

The started tasks can sleep. If a task is sleeping when a new task arrives
then the sleep is cancelled.

Workflow:
1. run(task) or async_run(task)
2. Task is started.
3. Task can do any async operation.
4. async_sleep().
5. Task can do any async operation.
6. Task is done.

It is guaranteed that step 2-6 cannot overlap with other tasks. It is also
guaranteed that a new task cancels only the async_sleep() operation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import contextlib
from typing import Any


class AsyncSequencer:
    """The AsyncSequencer implementation. Multiple instances can be created."""

    def __init__(self, loop: asyncio.EventLoop) -> None:
        """Create a new AsyncSequencer which runs the tasks on the passed EventLoop."""

        self._loop = loop

        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._sleep: asyncio.Task | None = None

    def __check_loop(self) -> None:
        if asyncio.get_running_loop() != self._loop:
            raise RuntimeError(f"Must be called from loop '{self._loop}'.")

    def __check_task(self) -> None:
        if asyncio.current_task() != self._task:
            raise RuntimeError("Must be called from run() or async_run().")

    @staticmethod
    async def __await(coro: Awaitable[None]) -> bool:
        try:
            await coro
        except asyncio.CancelledError:
            return False

        return True

    async def async_sleep(self, delay: float) -> bool:
        """Suspends the current task for the given period of time.

        It must be called from the coroutine which was passed to run() or
        async_run().
        """

        self.__check_loop()
        self.__check_task()

        sleep = asyncio.create_task(asyncio.sleep(delay))

        self._sleep = sleep
        status = await self.__await(sleep)
        self._sleep = None

        return status

    async def async_run(self, coro: Awaitable[Any]) -> None:
        """Run a coroutine asynchronously.

        It returns when the coroutine is done.
        """

        async with self._lock:
            # We are cancelling the previous task if it is sleeping,
            # otherwise letting it finish.
            sleep = self._sleep

            if sleep is not None:
                sleep.cancel()

            # Waiting for previous task.
            if self._task is not None:
                # the previous task can be successful or failed,
                # ignoring the return value/error
                with contextlib.suppress(Exception):
                    await self._task

            task: asyncio.Task = asyncio.create_task(coro)  # type: ignore[arg-type]

            self._task = task
            self._sleep = None

        await task

    def run(self, coro: Awaitable[Any]) -> None:
        """Run the coroutine in the background on the EventLoop.

        It returns immediately.
        """

        asyncio.run_coroutine_threadsafe(self.async_run(coro), self._loop)
