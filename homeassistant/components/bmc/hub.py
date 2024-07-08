"""Bali Muvek Controller and Home Assistant glue code."""

from __future__ import annotations

import logging
import random
import threading
from time import sleep
from typing import Callable

from homeassistant.components.bmc import DOMAIN
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# FIXME move somewhere else
PANEL_IO = 0x1
PANEL_1W = 0x2

def _check_address(address: int, device_type: int | None = None) -> None:
    bus = address >> 8

    if bus < 0 or bus > 1:
        raise ValueError("Invalid address '0x%03X', bus must be 0 or 1." % address)

    if device_type is not None and address >> 4 & 0xF != device_type:
        raise ValueError("Invalid address '0x%03X', expected device type '%d'." % (address, device_type))

def _get_io_input_resource(address: int, input: int) -> int:
    _check_address(address, PANEL_IO)

    if input < 0 or input > 5:
        raise ValueError(f"Wrong input '{input}', it must be between 0 and 5.")

    return address << 4 | input

def _get_io_output_resource(address: int, output: int) -> int:
    _check_address(address, PANEL_IO)

    if output < 0 or output > 5:
        raise ValueError(f"Wrong output '{output}', it must be between 0 and 5.")

    return address << 4 | 0x08 | output

def _get_1w_port_resource(address: int, port: int) -> int:
    _check_address(address, PANEL_1W)

    if port < 0 or port > 9:
        raise ValueError(f"Wrong port '{port}', it must be between 0 and 9.")

    return address << 4 | port

class BmcResource:
    def __init__(self, hub: BmcHub, resource: int) -> None:
        self._hub = hub
        self._resource = resource

        hub.use_resource(resource)

    def release(self) -> None:
        self._hub.release_resource(self._resource)

class BmcIoInput(BmcResource):
    def __init__(self, hub: BmcHub, address: int, input: int,
                 invert: bool, callback: Callable[[], None]) -> None:
        super().__init__(hub, _get_io_input_resource(address, input))

        self._address = address
        self._input = input
        self._invert = invert
        self._callback = callback

        # FIXME
        self._event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._event.is_set():
            sleep(5)
            self._callback()

    def read(self) -> bool:
        _LOGGER.info("Reading resource '0x%04X'." % self._resource)

        value = random.choice([False, True])

        if self._invert:
            return not value
        else:
            return value

    def release(self) -> None:
        _LOGGER.info("Closing background thread.")

        self._event.set()
        self._thread.join()

        super().release()

class BmcIoOutput(BmcResource):
    def __init__(self, hub: BmcHub, address: int, output: int,
                 pwm: bool, invert: bool) -> None:
        super().__init__(hub, _get_io_output_resource(address, output))

        self._address = address
        self._output = output
        self._pwm = pwm
        self._invert = invert

    def write(self, value: int) -> None:
        int_value = int(value)

        if not self._pwm and int_value != 0 and int_value != 255:
            raise ValueError(f"Wrong value '{int_value}'. It must be 0 or 255 if PWM is not enabled.")

        if int_value < 0 or int_value > 255:
            raise ValueError(f"Wrong value '{int_value}', it must be between 0 and 255.")

        if self._invert:
            int_value = 255 - int_value

        _LOGGER.info("Changing resource '0x%04X' to value '%s'." % (self._resource, int_value))

    def on(self, value: int = 255) -> None:
        if value == 0:
            raise ValueError(f"Wrong value '{value}'. It must be greater than 0.")

        self.write(value)

    def off(self) -> None:
        self.write(0)

class Bmc1wPort(BmcResource):
    def __init__(self, hub: BmcHub, address: int, port: int,
                 callback: Callable[[], None]) -> None:
        super().__init__(hub, _get_1w_port_resource(address, port))

        self._address = address
        self._port = port
        self._callback = callback

        # FIXME
        self._event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._event.is_set():
            sleep(5)
            self._callback()

    def read(self) -> float:
        _LOGGER.info("Reading resource '0x%04X'.", self._resource)

        return random.choice([22, 22.5, 23])

    def release(self) -> None:
        _LOGGER.info("Closing background thread.")

        self._event.set()
        self._thread.join()

        super().release()

class BmcHub:
    def __init__(self):
        self._resources = set()

    @staticmethod
    def get(hass: HomeAssistant) -> BmcHub:
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = BmcHub()

        return hass.data[DOMAIN]

    def _is_resource_available(self, resource: int) -> bool:
        return resource not in self._resources

    def is_io_input_available(self, address: int, input: int) -> bool:
        return self._is_resource_available(_get_io_input_resource(address, input))

    def is_io_output_available(self, address: int, output: int) -> bool:
        return self._is_resource_available(_get_io_output_resource(address, output))

    def is_1w_port_available(self, address: int, port: int) -> bool:
        return self._is_resource_available(_get_1w_port_resource(address, port))

    def use_resource(self, resource: int) -> None:
        if not self._is_resource_available(resource):
            raise ValueError("Resource is already used.")

        _LOGGER.info("Using resource '0x%04X'." % resource)

        self._resources.add(resource)

    def release_resource(self, resource: int) -> None:
        _LOGGER.info("Releasing resource '0x%04X'." % resource)

        self._resources.remove(resource)

    def use_io_input(
            self, address: int, input: int, invert: bool, callback: Callable[[], None]) -> BmcIoInput:
        return BmcIoInput(self, address, input, invert, callback)

    def use_io_output(
            self, address: int, output: int, pwm: bool, invert: bool) -> BmcIoOutput:
        return BmcIoOutput(self, address, output, pwm, invert)

    def use_1w_port(
            self, address: int, port: int, callback: Callable[[], None]) -> Bmc1wPort:
        return Bmc1wPort(self, address, port, callback)
