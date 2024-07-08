"""Asynchronous cancellable sleeping utility."""

import asyncio
import logging
from asyncio import CancelledError
from csv import excel

_LOGGER = logging.getLogger(__name__)

class Sleeper:
    def __init__(self):
        self._task = None

    @staticmethod
    async def _sleep_task(delay: float) -> None:
        await asyncio.sleep(delay)

    async def sleep(self, delay: float) -> bool:
        self._task = asyncio.create_task(self._sleep_task(delay))

        try:
            await self._task
        except CancelledError:
            return False
        finally:
            self._task = None

        return True

    def cancel(self) -> None:
        task = self._task

        if task is not None:
            task.cancel()
