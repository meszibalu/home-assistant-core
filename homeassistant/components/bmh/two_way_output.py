"""Two-Way device (cover, valve) support.

A Two-Way device can be opened (1) or closed (0). Some devices also support
inner positions. These devices might not traverse immediately between the
states, so opening and closing timeout can be defined.
"""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Awaitable, Callable
from enum import IntEnum, StrEnum
import logging

from .async_sequencer import AsyncSequencer
from .hub import BmhHub

_LOGGER = logging.getLogger(__name__)


class TwoWayOutputType(StrEnum):
    """Supported Two-Way output types."""

    NORMALLY_CLOSED = "Normally closed"
    NORMALLY_OPENED = "Normally opened"
    PWM = "PWM"
    TWO_DIRECTION = "Two direction"


class TwoWayOutputState(IntEnum):
    """Two-Way output state."""

    STOPPED = 0
    OPENING = 1
    CLOSING = 2


class TwoWayOutput:
    """Generic Two-Way output class."""

    def __init__(
        self,
        loop: asyncio.EventLoop,
        initial_position: float,
        timeout_open: float,
        timeout_close: float,
        on_change: Callable[[], None],
    ) -> None:
        """Initialize Two-Way output class."""

        self._loop = loop

        self._timeout_open = timeout_open
        self._timeout_close = timeout_close

        self._state: TwoWayOutputState | None = TwoWayOutputState.STOPPED
        self._position: float | None = initial_position
        self._on_change = on_change

        self._move_sequencer = AsyncSequencer(loop)
        self._on_change_sequencer = AsyncSequencer(loop)

    @staticmethod
    def _check_position(position: float) -> None:
        if position < 0 or position > 1:
            raise ValueError(
                f"Wrong position '{position}', it must be between 0 and 1."
            )

    @property
    def opening(self) -> bool | None:
        """Check if the device is opening."""

        if self._state is None:
            return None
        return self._state == TwoWayOutputState.OPENING

    @property
    def closing(self) -> bool | None:
        """Check if the device is closing."""

        if self._state is None:
            return None
        return self._state == TwoWayOutputState.CLOSING

    @property
    def position(self) -> float | None:
        """Return the device current position between 0 and 1."""

        return self._position

    def _set(
        self, state: TwoWayOutputState | None = None, position: float | None = None
    ) -> None:
        call_on_change = False

        if state is not None:
            if self._state != state:
                self._state = state
                call_on_change = True

        if position is not None:
            if self._position != position:
                self._position = position
                call_on_change = True

        if call_on_change:
            self._loop.call_soon(self._on_change)

    def _set_error(self) -> None:
        call_on_change = False

        if self._state is not None:
            self._state = None
            call_on_change = True

        if self._position is not None:
            self._position = None
            call_on_change = True

        if call_on_change:
            self._loop.call_soon(self._on_change)

    async def __async_on_error(self, error: Exception) -> None:
        _LOGGER.error("I/O error occurred on two way device", exc_info=error)

        self._set_error()

    def _on_error(self, error: Exception) -> None:
        self._run_on_change(self.__async_on_error(error))

    def _run_on_change(self, coro: Awaitable[None]) -> None:
        self._on_change_sequencer.run(coro)

    async def _async_move_sleep(self, timeout: float) -> None:
        await self._move_sequencer.async_sleep(timeout)

    async def _async_on_change_sleep(self, timeout: float) -> None:
        await self._on_change_sequencer.async_sleep(timeout)

    @abstractmethod
    async def _async_move(self, position: float) -> None:
        pass

    def move(self, position: float) -> None:
        """Move the device to the given position in the background.

        It returns immediately.
        """

        self._check_position(position)

        self._move_sequencer.run(self._async_move(position))

    async def async_move(self, position: float) -> None:
        """Move the device to the given position.

        It is device specific when it returns the control.
        """

        self._check_position(position)

        await self._move_sequencer.async_run(self._async_move(position))

    async def _async_stop(self) -> None:
        # an empty function is enough to cancel the previous task and wait
        pass

    def stop(self) -> None:
        """Stop device moving in the background.

        It returns immediately.
        """

        self._move_sequencer.run(self._async_stop())

    async def async_stop(self) -> None:
        """Stop device moving.

        It returns when stopping is finished.
        """

        await self._move_sequencer.async_run(self._async_stop())

    @staticmethod
    def create(
        hub: BmhHub,
        output_type: TwoWayOutputType,
        address: int,
        output: int,
        invert: bool,
        timeout: float,
        address2: int,
        output2: int,
        invert2: bool,
        timeout2: float,
        on_change: Callable[[], None],
    ) -> TwoWayOutput:
        """Create the specific Two-Way device.

        The device must be opened before usage.
        """

        match output_type:
            case TwoWayOutputType.NORMALLY_CLOSED:
                return TwoWayNormallyClosed(
                    hub, address, output, invert, timeout, timeout2, on_change
                )
            case TwoWayOutputType.NORMALLY_OPENED:
                return TwoWayNormallyOpened(
                    hub, address, output, invert, timeout, timeout2, on_change
                )
            case TwoWayOutputType.PWM:
                return TwoWayPwm(
                    hub, address, output, invert, timeout, timeout2, on_change
                )
            case TwoWayOutputType.TWO_DIRECTION:
                return TwoWayTwoDirection(
                    hub,
                    address,
                    output,
                    invert,
                    timeout,
                    address2,
                    output2,
                    invert2,
                    timeout2,
                    on_change,
                )
            case _:
                raise ValueError(f"Unknown output type '{output_type}'.")

    @abstractmethod
    async def async_open(self) -> None:
        """Open the Two-Way device."""

    @abstractmethod
    async def async_release(self) -> None:
        """Release the Two-Way device."""


class TwoWayNormallyClosed(TwoWayOutput):
    """Normally Closed (NC) device implementation.

    An NC device requires one I/O Output. If the output is switched off then
    the device is closed.
    """

    def __init__(
        self,
        hub: BmhHub,
        address: int,
        output: int,
        invert: bool,
        timeout_open: float,
        timeout_close: float,
        on_change: Callable[[], None],
    ) -> None:
        """Initialize an NC device."""

        super().__init__(hub.loop, 0, timeout_open, timeout_close, on_change)

        self._io_output = hub.create_io_output(
            address, output, False, invert, self.__io_on_change, self._on_error
        )

    async def async_open(self) -> None:
        """Open I/O Output.

        The I/O Output is switched off (closed).
        """

        await self._io_output.async_open()
        await self._io_output.async_off()

    async def __async_io_on_change(self, value: int) -> None:
        if value == 0:
            self._set(state=TwoWayOutputState.CLOSING)

            try:
                await self._async_on_change_sleep(self._timeout_close)
            finally:
                self._set(state=TwoWayOutputState.STOPPED, position=0)
        elif value == 255:
            self._set(state=TwoWayOutputState.OPENING)

            try:
                await self._async_on_change_sleep(self._timeout_open)
            finally:
                self._set(state=TwoWayOutputState.STOPPED, position=1)
        else:
            _LOGGER.error("Invalid I/O state '%d' for normally closed device", value)
            await self._io_output.async_off()

    def __io_on_change(self, value: int) -> None:
        self._run_on_change(self.__async_io_on_change(value))

    async def _async_move(self, position: float) -> None:
        if position == 0:
            await self._io_output.async_off()
        elif position == 1:
            await self._io_output.async_on()
        else:
            raise ValueError(f"Normally closed does not support position '{position}'.")

    async def async_release(self) -> None:
        """Release the I/O.

        The device is moved to the normal position.
        """

        await self._io_output.async_off()
        await self._io_output.async_release()


class TwoWayNormallyOpened(TwoWayOutput):
    """Normally Opened (NO) device implementation.

    An NO device requires one I/O Output. If the output is switched off then
    the device is opened.
    """

    def __init__(
        self,
        hub: BmhHub,
        address: int,
        output: int,
        invert: bool,
        timeout_open: float,
        timeout_close: float,
        on_change: Callable[[], None],
    ) -> None:
        """Initialize an NO device."""

        super().__init__(hub.loop, 1, timeout_open, timeout_close, on_change)

        self._io_output = hub.create_io_output(
            address, output, False, invert, self.__io_on_change, None
        )

    async def async_open(self) -> None:
        """Open I/O Output.

        The I/O Output is switched off (opened).
        """

        await self._io_output.async_open()
        await self._io_output.async_off()

    async def __async_io_on_change(self, value: int) -> None:
        if value == 0:
            self._set(state=TwoWayOutputState.OPENING)

            try:
                await self._async_on_change_sleep(self._timeout_open)
            finally:
                self._set(state=TwoWayOutputState.STOPPED, position=1)
        elif value == 255:
            self._set(state=TwoWayOutputState.CLOSING)

            try:
                await self._async_on_change_sleep(self._timeout_close)
            finally:
                self._set(state=TwoWayOutputState.STOPPED, position=0)
        else:
            _LOGGER.error("Invalid I/O state '%d' for normally opened device", value)
            await self._io_output.async_off()

    def __io_on_change(self, value: int) -> None:
        self._run_on_change(self.__async_io_on_change(value))

    async def _async_move(self, position: float) -> None:
        if position == 0:
            await self._io_output.async_on()
        elif position == 1:
            await self._io_output.async_off()
        else:
            raise ValueError(f"Normally opened does not support position '{position}'.")

    async def async_release(self) -> None:
        """Release the I/O.

        The device is moved to the normal position.
        """

        await self._io_output.async_off()
        await self._io_output.async_release()


class TwoWayPwm(TwoWayOutput):
    """PWM device implementation.

    A PWM device requires one I/O Output. If the output is switched off then
    the device is closed. The openness of the device is proportional to the
    duty cycle.
    """

    def __init__(
        self,
        hub: BmhHub,
        address: int,
        output: int,
        invert: bool,
        timeout_open: float,
        timeout_close: float,
        on_change: Callable[[], None],
    ) -> None:
        """Initialize a PWM device."""

        super().__init__(hub.loop, 0, timeout_open, timeout_close, on_change)

        self._io_output = hub.create_io_output(
            address, output, True, invert, self.__io_on_change, self._on_error
        )

    async def async_open(self) -> None:
        """Open I/O Output.

        The I/O Output is switched off (closed).
        """

        await self._io_output.async_open()
        await self._io_output.async_off()

    async def __async_io_on_change(self, value: int) -> None:
        position = value / 255

        if self._position is None:
            # recovery logic, immediately setting state without timeout
            self._set(state=TwoWayOutputState.STOPPED, position=position)
        elif position < self._position:
            self._set(state=TwoWayOutputState.CLOSING)

            timeout = (self._position - position) * self._timeout_close

            try:
                await self._async_on_change_sleep(timeout)
            finally:
                self._set(state=TwoWayOutputState.STOPPED, position=position)
        elif position > self._position:
            self._set(state=TwoWayOutputState.OPENING)

            timeout = (position - self._position) * self._timeout_open

            try:
                await self._async_on_change_sleep(timeout)
            finally:
                self._set(state=TwoWayOutputState.STOPPED, position=position)

    def __io_on_change(self, value: int) -> None:
        self._run_on_change(self.__async_io_on_change(value))

    async def _async_move(self, position: float) -> None:
        value = round(position * 255)
        await self._io_output.async_write(value)

    async def async_release(self) -> None:
        """Release the I/O.

        The device is moved to closed position.
        """

        await self._io_output.async_off()
        await self._io_output.async_release()


class TwoWayTwoDirection(TwoWayOutput):
    """Two direction device implementation.

    A two direction device requires two I/O Outputs, one for opening and
    one for closing. When the two outputs are off then the device is not
    moving. If one of the outputs is on then the device is opening or closing.

    The actual position is tracked based on the elapsed time, so it can be
    inaccurate after some commands. Position 0 (closed) and 1 (opened)
    are handled differently for this reason. They run for the full timeout
    for ensuring the accurate state.

    The position in the initial state is unknown, but it is initialized as
    fully opened.
    """

    def __init__(
        self,
        hub: BmhHub,
        address_open: int,
        output_open: int,
        invert_open: bool,
        timeout_open: float,
        address_close: int,
        output_close: int,
        invert_close: bool,
        timeout_close: float,
        on_change: Callable[[], None],
    ) -> None:
        """Initialize a two direction device."""

        super().__init__(hub.loop, 1, timeout_open, timeout_close, on_change)

        self._start_time: float | None = None
        self.__stop_condition = asyncio.Condition()

        self._io_output_open = hub.create_io_output(
            address_open,
            output_open,
            False,
            invert_open,
            self.__open_on_change,
            self._on_error,
        )
        self._io_output_close = hub.create_io_output(
            address_close,
            output_close,
            False,
            invert_close,
            self.__close_on_change,
            self._on_error,
        )

    async def async_open(self) -> None:
        """Open I/O Output.

        The I/O Outputs are switched off, so the device is stopped.
        """

        await self._io_output_open.async_open()
        await self._io_output_close.async_open()

        await self._io_output_open.async_off()
        await self._io_output_close.async_off()

    async def __async_open(self) -> None:
        await self._io_output_close.async_off()
        await self._io_output_open.async_on()

    async def __async_close(self) -> None:
        await self._io_output_open.async_off()
        await self._io_output_close.async_on()

    async def __async_stop(self) -> None:
        await self._io_output_open.async_off()
        await self._io_output_close.async_off()

    def __set_move_start(self, state: TwoWayOutputState) -> None:
        self._start_time = self._loop.time()
        self._set(state=state)

    async def __async_set_move_end(self) -> None:
        if self._start_time is None:
            elapsed = 0.0
        else:
            elapsed = self._loop.time() - self._start_time

        self._start_time = None

        match self._state:
            case None:
                delta = 0.0
            case TwoWayOutputState.STOPPED:
                delta = 0.0
            case TwoWayOutputState.OPENING:
                if self._timeout_open > 0.0:
                    delta = elapsed / self._timeout_open
                else:
                    delta = 1.0
            case TwoWayOutputState.CLOSING:
                if self._timeout_close > 0.0:
                    delta = -elapsed / self._timeout_close
                else:
                    delta = -1.0

        # The elapsed time is the time between the NOTICED output change,
        # so there can be a small difference between it and the sleep time.
        # If the position is within 0.5% to the fully opened/closed state then
        # we consider it as fully opened/closed.
        # 0.5% is the rounding error on the UI.
        if self._position is None:
            if delta >= 0.995:
                position = 1.0
            elif delta <= -0.995:
                position = 0.0
            else:
                # the movement was not a full one, position remains unknown
                position = None

                _LOGGER.warning(
                    "Two direction device was moved, but the "
                    "original position was unknown and the moving "
                    "time was not a full open/close, so the "
                    "position remains unknown"
                )
        else:
            position = self._position + delta

            if position < 0.005:
                position = 0
            elif position > 0.995:
                position = 1

        self._set(state=TwoWayOutputState.STOPPED, position=position)

        async with self.__stop_condition:
            self.__stop_condition.notify_all()

    async def __async_open_on_change(self, value: int) -> None:
        if value not in (0, 255):
            _LOGGER.error("Invalid I/O state '%d' for two way device", value)
            await self.__async_stop()
            await self.__async_set_move_end()

            return

        stopped = value == 0
        started = value != 0

        match self._state:
            case None:
                # the device is in unknown state, we try to recover
                if stopped:
                    await self.__async_set_move_end()
                else:
                    # the device started to open, we must ensure close is off
                    await self._io_output_close.async_off()
                    self.__set_move_start(TwoWayOutputState.OPENING)
            case TwoWayOutputState.STOPPED:
                if stopped:
                    # it is a recovery step from a previous error
                    await self.__async_set_move_end()
                else:
                    self.__set_move_start(TwoWayOutputState.OPENING)
            case TwoWayOutputState.OPENING:
                if stopped:
                    await self.__async_set_move_end()
            case TwoWayOutputState.CLOSING:
                if started:
                    _LOGGER.error("Open cannot be on while closing")
                    await self.__async_stop()
                    await self.__async_set_move_end()

    async def __async_close_on_change(self, value: int) -> None:
        if value not in (0, 255):
            _LOGGER.error("Invalid I/O state '%d' for two way device", value)
            await self.__async_stop()
            await self.__async_set_move_end()

            return

        stopped = value == 0
        started = value != 0

        match self._state:
            case None:
                # the device is in unknown state, we try to recover
                if stopped:
                    await self.__async_set_move_end()
                else:
                    # the device started to close, we must ensure open is off
                    await self._io_output_open.async_off()
                    self.__set_move_start(TwoWayOutputState.CLOSING)
            case TwoWayOutputState.STOPPED:
                if stopped:
                    # it is a recovery step from a previous error
                    await self.__async_set_move_end()
                else:
                    self.__set_move_start(TwoWayOutputState.CLOSING)
            case TwoWayOutputState.OPENING:
                if started:
                    _LOGGER.error("Close cannot be on while opening")
                    await self.__async_stop()
                    await self.__async_set_move_end()
            case TwoWayOutputState.CLOSING:
                if stopped:
                    await self.__async_set_move_end()

    def __open_on_change(self, value: int) -> None:
        self._run_on_change(self.__async_open_on_change(value))

    def __close_on_change(self, value: int) -> None:
        self._run_on_change(self.__async_close_on_change(value))

    async def _async_move(self, position: float) -> None:
        # We cancel the previous movement before entering this method,
        # however the interrupt (__*_on_change) can arrive later.
        # We are waiting for some time for the interrupt to arrive.
        # If it does not arrive, we are proceeding and actuating
        # the outputs anyway.
        try:
            async with self.__stop_condition:
                aw = self.__stop_condition.wait_for(
                    lambda: self._state is None
                    or self._state == TwoWayOutputState.STOPPED
                )

                await asyncio.wait_for(aw, 0.1)
        except TimeoutError:
            _LOGGER.warning("Output has not been stopped in 100 ms")

        # position=0 and position=1 handled differently,
        # we are switching on the output for the full timeout
        if position == 0:
            await self.__async_close()
            timeout = self._timeout_close
        elif position == 1:
            await self.__async_open()
            timeout = self._timeout_open
        elif self._position is None:
            raise OSError(
                "Device position is unknown, only fully opening or closing is possible"
            )
        elif position < self._position:
            await self.__async_close()
            timeout = (self._position - position) * self._timeout_close
        elif position > self._position:
            await self.__async_open()
            timeout = (position - self._position) * self._timeout_open
        else:
            return

        await self._async_move_sleep(timeout)

        await self.__async_stop()

    async def async_release(self) -> None:
        """Release the I/O.

        The device is stopped and is left in that state.
        """

        await self.async_stop()

        await self._io_output_open.async_release()
        await self._io_output_close.async_release()
