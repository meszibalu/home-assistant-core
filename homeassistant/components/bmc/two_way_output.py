"""Two-way output handling utils."""

from __future__ import annotations

import time
from abc import abstractmethod
from enum import StrEnum

from homeassistant.components.bmc import BmcHub
from homeassistant.components.bmc.hub import BmcIoOutput
from homeassistant.components.bmc.sleeper import Sleeper


class TwoWayOutputType(StrEnum):
    """Output control type for covers and valves."""

    NORMALLY_OPEN = "Normally open"
    NORMALLY_CLOSED = "Normally closed"
    PWM = "PWM"
    TWO_DIRECTION = "Two direction"

class TwoWayOutput:
    def __init__(self, initial_position: float, timeout_open: float, timeout_close: float) -> None:
        self._timeout_open = timeout_open
        self._timeout_close = timeout_close

        self._position = initial_position
        self._sleeper = Sleeper()

    @property
    def position(self) -> float:
        return self._position

    @staticmethod
    def _check_position(position: float) -> None:
        if position < 0 or position > 100:
            raise ValueError(f"Wrong position '{position}', it must be between 0 and 100.")

    async def sleep(self, delay: float) -> (float, bool):
        return await self._sleeper.sleep(delay)

    def cancel(self) -> None:
        self._sleeper.cancel()

    @abstractmethod
    async def async_move(self, position: float) -> bool:
        pass

    @staticmethod
    def open(hub: BmcHub, output_type: TwoWayOutputType,
             address: int, output: int, invert: bool, timeout: float,
             address2: int, output2: int, invert2: bool, timeout2: float) -> TwoWayOutput:
        match output_type:
            case TwoWayOutputType.NORMALLY_OPEN:
                return TwoWayNormallyOpen(hub, address, output, invert, timeout, timeout2)
            case TwoWayOutputType.NORMALLY_CLOSED:
                return TwoWayNormallyClosed(hub, address, output, invert, timeout, timeout2)
            case TwoWayOutputType.PWM:
                return TwoWayPwm(hub, address, output, invert, timeout, timeout2)
            case TwoWayOutputType.TWO_DIRECTION:
                return TwoWayTwoDirection(hub, address, output, invert, timeout,
                                          address2, output2, invert2, timeout2)

    @abstractmethod
    def release(self) -> None:
        pass

class TwoWayNormallyOpen(TwoWayOutput):
    def __init__(self, hub: BmcHub,
                 address: int, output: int, invert: bool, timeout_open: float, timeout_close: float) -> None:
        super().__init__(100, timeout_open, timeout_close)

        self._io_output = BmcIoOutput(hub, address, output, False, invert)
        self._io_output.off()

    async def async_move(self, position: float) -> bool:
        self._check_position(position)

        if position == 0:
            self._io_output.on()
            done = await self.sleep(self._timeout_close)
        elif position == 100:
            self._io_output.off()
            done = await self.sleep(self._timeout_open)
        else:
            raise ValueError(f"Normally open does not support position '{position}'.")

        self._position = position

        return done

    def release(self) -> None:
        # returning to normal position
        self._io_output.off()
        self._io_output.release()

class TwoWayNormallyClosed(TwoWayOutput):
    def __init__(self, hub: BmcHub,
                 address: int, output: int, invert: bool, timeout_open: float, timeout_close: float) -> None:
        super().__init__(0, timeout_open, timeout_close)

        self._io_output = BmcIoOutput(hub, address, output, False, invert)
        self._io_output.off()

    async def async_move(self, position: float) -> bool:
        self._check_position(position)

        if position == 0:
            self._io_output.off()
            done = await self.sleep(self._timeout_close)
        elif position == 100:
            self._io_output.on()
            done = await self.sleep(self._timeout_open)
        else:
            raise ValueError(f"Normally closed does not support position '{position}'.")

        self._position = position

        return done

    def release(self) -> None:
        # returning to normal position
        self._io_output.off()
        self._io_output.release()

class TwoWayPwm(TwoWayOutput):
    def __init__(self, hub: BmcHub,
                 address: int, output: int, invert: bool, timeout_open: float, timeout_close: float) -> None:
        super().__init__(0, timeout_open, timeout_close)

        self._io_output = BmcIoOutput(hub, address, output, True, invert)
        self._io_output.off()

    async def async_move(self, position: float) -> None:
        self._check_position(position)

        value = int(position * 255 / 100)
        self._io_output.write(value)

        if position < self._position:
            timeout = (self._position - position) / 100 * self._timeout_open
            done = await self.sleep(timeout)
        elif position > self._position:
            timeout = (position - self._position) / 100 * self._timeout_close
            done = await self.sleep(timeout)
        else:
            return

        self._position = position

        return done

    def release(self) -> None:
        self._io_output.off()
        self._io_output.release()

class TwoWayTwoDirection(TwoWayOutput):
    def __init__(self, hub: BmcHub,
                 address_open: int, output_open: int, invert_open: bool, timeout_open: float,
                 address_close: int, output_close: int, invert_close: bool, timeout_close: float) -> None:
        super().__init__(100, timeout_open, timeout_close)

        self._io_output_open = BmcIoOutput(hub, address_open, output_open, False, invert_open)
        self._io_output_close = BmcIoOutput(hub, address_close, output_close, False, invert_close)

        self._stop()

    def _open(self) -> None:
        self._io_output_close.off()
        self._io_output_open.on()

    def _close(self) -> None:
        self._io_output_open.off()
        self._io_output_close.on()

    def _stop(self) -> None:
        self._io_output_open.off()
        self._io_output_close.off()

    async def async_move(self, position: float) -> bool:
        self._check_position(position)

        # position=0 and position=100 handled differently, we are switching on the output for the full timeout
        if position == 0:
            self._close()
            timeout = -self._timeout_close
            full_timeout = -self._timeout_close
        elif position == 100:
            self._open()
            timeout = self._timeout_open
            full_timeout = self._timeout_open
        elif position < self._position:
            self._close()
            timeout = (self._position - position) / 100 * -self._timeout_close
            full_timeout = -self._timeout_close
        elif position > self._position:
            self._open()
            timeout = (position - self._position) / 100 * self._timeout_open
            full_timeout = self._timeout_open
        else:
            return True

        start = time.monotonic()
        done = await self.sleep(abs(timeout))
        end = time.monotonic()

        self._stop()

        delta = (end - start) / full_timeout * 100
        new_position = self._position + delta

        if new_position < 0:
            new_position = 0
        elif new_position > 100:
            new_position = 100

        self._position = new_position

        return done

    def release(self) -> None:
        self._io_output_open.release()
        self._io_output_close.release()
