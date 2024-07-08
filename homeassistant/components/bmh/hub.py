"""Bali Művek Home Controller and Home Assistant glue code."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Any

import bmh

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant

from .strings import Strings

_LOGGER = logging.getLogger(__name__)

bmh.TRACE_MESSAGES = True


class BmhDevicePort:
    """Device and port representation.

    It is hashable can be used as map keys.
    """

    def __init__(
        self, address: int, port: int, str_function: Callable[[int, int], str]
    ) -> None:
        """Create device and port representation."""

        self._address = address
        self._port = port
        self._string = str_function(address, port)

    @property
    def address(self) -> int:
        """Return device address."""

        return self._address

    @property
    def port(self) -> int:
        """Return device port."""

        return self._port

    def __hash__(self) -> int:
        """Create hash of device port."""

        return hash(self._string)

    def __eq__(self, other) -> bool:
        """Check if the two device ports are equal."""
        return self._string == other._string

    def __ne__(self, other) -> bool:
        """Check if the two device ports are not equal."""

        return not self == other

    def __str__(self) -> str:
        """Return the string representation of this device port."""

        return self._string

    @staticmethod
    def _check_device_type(address: int, device_type: int) -> None:
        if address & bmh.PANEL_MASK != device_type:
            raise ValueError(
                f"Invalid address '{Strings.get_address(address)}', "
                f"expected device type '{device_type:X}'"
            )

    @staticmethod
    def get_io_input(address: int, port: int) -> BmhDevicePort:
        """Create BmhDevicePort for I/O input."""

        BmhDevicePort._check_device_type(address, bmh.PANEL_IO)

        if port < 0 or port > 5:
            raise ValueError(f"Wrong input '{port}', it must be between 0 and 5.")

        return BmhDevicePort(address, port, Strings.get_io_input)

    @staticmethod
    def get_io_output(address: int, port: int) -> BmhDevicePort:
        """Create BmhDevicePort for I/O output."""

        BmhDevicePort._check_device_type(address, bmh.PANEL_IO)

        if port < 0 or port > 5:
            raise ValueError(f"Wrong output '{port}', it must be between 0 and 5.")

        return BmhDevicePort(address, port, Strings.get_io_output)

    @staticmethod
    def get_1w_port(address: int, port: int) -> BmhDevicePort:
        """Create BmhDevicePort for 1-Wire port."""

        BmhDevicePort._check_device_type(address, bmh.PANEL_1W)

        if port < 0 or port > 9:
            raise ValueError(f"Wrong port '{port}', it must be between 0 and 9.")

        return BmhDevicePort(address, port, Strings.get_1w_port)


class BmhResource:
    """Base class for hub resources (I/O inputs, outputs, 1-Wire ports)."""

    def __init__(
        self, hub: BmhHub, device: bmh.Device, device_port: BmhDevicePort
    ) -> None:
        """Create the resource."""

        self._hub = hub
        self._device = device
        self._device_port = device_port

    @property
    def device(self) -> bmh.Device:
        """Return the associated BmhDevice."""

        return self._device

    @property
    def port(self) -> int:
        """Return the associated device port."""

        return self._device_port.port

    @property
    def device_port(self) -> BmhDevicePort:
        """Return the BmhDevicePort object for the resource."""

        return self._device_port

    async def async_release(self) -> None:
        """Release the resource."""

        await self._hub.async_release(self)


class BmhIoInput(BmhResource):
    """Hub resource implementation for I/O inputs."""

    def __init__(
        self,
        hub: BmhHub,
        device: bmh.Device,
        port: int,
        invert: bool,
        on_change: Callable[[bool], None],
    ) -> None:
        """Create I/O input resource."""

        super().__init__(hub, device, BmhDevicePort.get_io_input(device.id, port))

        self._invert = invert
        self._on_change = on_change

    def __read(self) -> None:
        _LOGGER.debug("Reading '%s'", self.device_port)

        inputs = self._device.get_inputs()
        value = inputs & (1 << self.port) != 0

        self.call_on_change(value)

    def read(self) -> None:
        """Schedule reading the input port in the background.

        The result is delegated to the on_change method.
        """

        self._hub.background_io(self.__read)

    def call_on_change(self, value: bool) -> None:
        """Call on_change method with the new input state."""

        _LOGGER.debug("'%s' changed to '%s'", self.device_port, value)

        callback = self._on_change

        if callback is None:
            return

        if self._invert:
            callback(not value)
        else:
            callback(value)


class BmhIoOutput(BmhResource):
    """Hub resource implementation for I/O outputs."""

    def __init__(
        self,
        hub: BmhHub,
        device: bmh.Device,
        port: int,
        pwm: bool,
        invert: bool,
        on_change: Callable[[int], None],
    ) -> None:
        """Create I/O output resource."""

        super().__init__(hub, device, BmhDevicePort.get_io_output(device.id, port))

        self._pwm = pwm
        self._invert = invert
        self._on_change = on_change

    def __read(self) -> None:
        _LOGGER.debug("Reading '%s'", self.device_port)

        value = self._device.get_output(self.port)

        self.call_on_change(value)

    def read(self) -> None:
        """Schedule reading the output port in the background.

        The result is delegated to the on_change method.
        """

        self._hub.background_io(self.__read)

    def __write(self, value: int) -> None:
        _LOGGER.info("Changing '%s' to '%d'", self.device_port, value)

        self._device.set_output(self.port, value)

    async def async_write(self, value: int) -> None:
        """Change output state in the background.

        The completion can be awaited.
        """

        int_value = int(value)

        if not self._pwm and int_value not in (0, 255):
            raise ValueError(
                f"Wrong value '{int_value}'. It must be 0 or 255 if PWM is not enabled."
            )

        if int_value < 0 or int_value > 255:
            raise ValueError(
                f"Wrong value '{int_value}'. It must be between 0 and 255."
            )

        if self._invert:
            int_value = 255 - int_value

        await self._hub.async_io(self.__write, int_value)

    async def async_on(self, value: int = 255) -> None:
        """Turn on output in the background.

        The completion can be awaited.
        """

        if value == 0:
            raise ValueError(f"Wrong value '{value}'. It must be greater than 0.")

        await self.async_write(value)

    async def async_off(self) -> None:
        """Turn off output in the background.

        The completion can be awaited.
        """

        await self.async_write(0)

    def call_on_change(self, value: int) -> None:
        """Call on_change method with the new output state."""

        _LOGGER.debug("'%s' changed to '%d'", self.device_port, value)

        callback = self._on_change

        if callback is None:
            return

        if self._invert:
            callback(255 - value)
        else:
            callback(value)


class Bmh1wPort(BmhResource):
    """Hub resource implementation for 1-Wire ports."""

    def __init__(
        self,
        hub: BmhHub,
        device: bmh.Device,
        port: int,
        on_change: Callable[[float | str | None], None],
    ) -> None:
        """Create 1-Wire port resource."""

        super().__init__(hub, device, BmhDevicePort.get_1w_port(device.id, port))

        self._on_change = on_change

    def __read(self) -> None:
        _LOGGER.debug("Reading '%s'", self.device_port)

        temperature = self._device.get_temperature(self.port)

        self.call_on_change(temperature)

    def read(self) -> None:
        """Schedule reading the 1-Wire port in the background.

        The result is delegated to the on_change method.
        """

        self._hub.background_io(self.__read)

    def call_on_change(self, temperature: float | str | None) -> None:
        """Call on_change method with the new 1-Wire port value."""

        _LOGGER.debug("'%s' changed to '%s'", self.device_port, temperature)

        callback = self._on_change

        if callback is None:
            return

        callback(temperature)


class BmhHub:
    """Bali Művek Home Controller hub for managing devices from Home Assistant."""

    _instance_lock = asyncio.Lock()
    _instance: BmhHub | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Create a new hub.

        Consider using async_get() instead.
        """

        self._hass = hass
        self._lock = asyncio.Lock()
        self._resources: dict[BmhDevicePort, BmhResource] = {}

        self._handle = bmh.Bmh()

        self._io_pool = ThreadPoolExecutor(1, thread_name_prefix="BmhHubIO")

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Return Home Assistant event loop."""

        return self._hass.loop

    def background_io[*Ts](self, function: Callable[[*Ts], Any], *args: *Ts) -> None:
        """Run an I/O task in the background."""

        self._io_pool.submit(function, *args)

    async def async_io[R, *Ts](self, function: Callable[[*Ts], R], *args: *Ts) -> R:
        """Run an I/O task in the background. The result can be awaited."""

        return await self.loop.run_in_executor(self._io_pool, function, *args)

    # pylint: disable=unused-private-member
    def __check_devices(self) -> None:
        version_mismatch_devices = []

        for device in self._handle.scan():
            if device.version != bmh.VERSION:
                address_string = f"{Strings.get_address(device.id)} ({device.version})"
                version_mismatch_devices.append(address_string)

            # clearing reset interrupt
            device.get_reset()

        if len(version_mismatch_devices) > 0:
            devices_string = ",\n".join(version_mismatch_devices)

            self.notify(
                "Version mismatch",
                "Some devices do not have the most recent version "
                f"({bmh.VERSION}):\n{devices_string}",
            )

    @staticmethod
    async def async_get(hass: HomeAssistant) -> BmhHub:
        """Get the hub singleton for Home Assistant."""

        if BmhHub._instance is not None:
            return BmhHub._instance

        async with BmhHub._instance_lock:
            if BmhHub._instance is not None:
                return BmhHub._instance

            _LOGGER.info("Opening hub")

            hub = BmhHub(hass)
            await hub.async_io(hub.__check_devices)

            BmhHub._instance = hub

            return BmhHub._instance

    def __notify_unsafe(self, title: str, message: str) -> None:
        persistent_notification.async_create(self._hass, message, "[BMH] " + title)

    def notify(self, title: str, message: str) -> None:
        """Notify the user about something."""

        _LOGGER.warning(message)

        self.loop.call_soon_threadsafe(self.__notify_unsafe, title, message)

    def __is_device_port_available(self, device_port: BmhDevicePort) -> bool:
        return device_port not in self._resources

    def __check_device_port_available(self, device_port: BmhDevicePort) -> None:
        if not self.__is_device_port_available(device_port):
            raise ValueError(f"Device port '{device_port}' is already used.")

    def is_io_input_available(self, address: int, port: int) -> bool:
        """Check if the I/O input is available or it is already assigned."""

        return self.__is_device_port_available(
            BmhDevicePort.get_io_input(address, port)
        )

    def is_io_output_available(self, address: int, port: int) -> bool:
        """Check if the I/O output is available or it is already assigned."""

        return self.__is_device_port_available(
            BmhDevicePort.get_io_output(address, port)
        )

    def is_1w_port_available(self, address: int, port: int) -> bool:
        """Check if the 1-Wire port is available or it is already assigned."""

        return self.__is_device_port_available(BmhDevicePort.get_1w_port(address, port))

    async def async_check_device_present(self, address: int) -> None:
        """Check if the device is present or not."""

        await self.async_io(self._handle.get_device, address)

    def __on_io_interrupt(self, device: bmh.DeviceIo, status: int) -> int:
        handled = 0

        if status & bmh.DeviceIo.INPUT_INTERRUPT_CHANNELS:
            handled |= bmh.DeviceIo.INPUT_INTERRUPT_CHANNELS
            inputs = device.get_inputs()

            for port in range(6):
                if not status & bmh.DeviceIo.INPUT_INTERRUPT_CHANNEL(port):
                    continue

                device_port = BmhDevicePort.get_io_input(device.id, port)

                if device_port not in self._resources:
                    continue

                value = bool(inputs & (1 << port))

                resource = self._resources[device_port]
                resource.call_on_change(value)  # type: ignore[attr-defined]

        if status & bmh.DeviceIo.OUTPUT_INTERRUPT_CHANNELS:
            handled |= bmh.DeviceIo.OUTPUT_INTERRUPT_CHANNELS

            for port in range(6):
                if not status & bmh.DeviceIo.OUTPUT_INTERRUPT_CHANNEL(port):
                    continue

                # we have to read output to clear interrupt
                value = device.get_output(port)

                device_port = BmhDevicePort.get_io_output(device.id, port)

                if device_port not in self._resources:
                    continue

                resource = self._resources[device_port]
                resource.call_on_change(value)  # type: ignore[attr-defined]

        if status & bmh.DeviceIo.BACKUP_MODE_INTERRUPT_CHANNEL:
            handled |= bmh.DeviceIo.BACKUP_MODE_INTERRUPT_CHANNEL

            device_string = Strings.get_type_address(device.id)
            backup_mode = device.is_backup_mode()

            self.notify(
                "Backup mode",
                f"Device '{device_string}' changed backup mode: {backup_mode}",
            )

        return handled

    def __on_1w_interrupt(self, device: bmh.Device1w, status: int) -> int:
        for port in range(10):
            if not status & bmh.Device1w.PORT_INTERRUPT_CHANNEL(port):
                continue

            # we have to read temperature to clear interrupt
            temperature = device.get_temperature(port)

            device_port = BmhDevicePort.get_1w_port(device.id, port)

            if device_port not in self._resources:
                continue

            resource = self._resources[device_port]
            resource.call_on_change(temperature)  # type: ignore[attr-defined]

        return bmh.Device1w.PORT_INTERRUPT_CHANNELS

    def __on_interrupt(self, device: bmh.Device, status: int) -> None:
        handled = 0

        match device:
            case bmh.DeviceIo():
                handled |= self.__on_io_interrupt(device, status)
            case bmh.Device1w():
                handled |= self.__on_1w_interrupt(device, status)

        if status & bmh.Device.RESET_INTERRUPT_CHANNEL:
            handled |= bmh.Device.RESET_INTERRUPT_CHANNEL

            device_string = Strings.get_address(device.id)
            reset = device.get_reset()

            if reset is None:
                reason = "UNKNOWN"
            else:
                reason = reset.name

            self.notify("Reset", f"Device '{device_string}' was reset: {reason}")

            if device.version != bmh.VERSION:
                self.notify(
                    "Version mismatch",
                    f"Device '{device_string}' ({device.version}) "
                    "does not have the most recent version "
                    f"({bmh.VERSION})",
                )

        not_handled = status & ~handled

        if not_handled != 0:
            device_string = Strings.get_address(device.id)

            # A device with unhandled interrupt channel will appear in
            # every interrupt search which might slow down interrupt
            # handling and response time.
            _LOGGER.warning(
                "Device '%s' has unhandled interrupts '0x%04X'",
                device_string,
                not_handled,
            )

    def __use_resource(self, resource: BmhResource) -> None:
        self.__check_device_port_available(resource.device_port)

        _LOGGER.debug("Using device port '%s'", resource.device_port)

        bus = resource.device.bus

        if bus.interrupt_handler is None:
            bus.interrupt_handler = self.__on_interrupt

        self._resources[resource.device_port] = resource

    def __open_io_input(
        self, address: int, port: int, invert: bool, on_change: Callable[[bool], None]
    ) -> BmhIoInput:
        device = self._handle.get_device(address)
        resource = BmhIoInput(self, device, port, invert, on_change)

        self.__use_resource(resource)

        return resource

    def __open_io_output(
        self,
        address: int,
        port: int,
        pwm: bool,
        invert: bool,
        on_change: Callable[[int], None],
    ) -> BmhIoOutput:
        device = self._handle.get_device(address)
        resource = BmhIoOutput(self, device, port, pwm, invert, on_change)

        self.__use_resource(resource)

        return resource

    def __open_1w_port(
        self, address: int, port: int, on_change: Callable[[float | str | None], None]
    ) -> Bmh1wPort:
        device = self._handle.get_device(address)
        resource = Bmh1wPort(self, device, port, on_change)

        self.__use_resource(resource)

        return resource

    async def async_open_io_input(
        self, address: int, port: int, invert: bool, on_change: Callable[[bool], None]
    ) -> BmhIoInput:
        """Open and use an I/O input device."""

        async with self._lock:
            return await self.async_io(
                self.__open_io_input, address, port, invert, on_change
            )

    async def async_open_io_output(
        self,
        address: int,
        port: int,
        pwm: bool,
        invert: bool,
        on_change: Callable[[int], None],
    ) -> BmhIoOutput:
        """Open and use an I/O output device."""

        async with self._lock:
            return await self.async_io(
                self.__open_io_output, address, port, pwm, invert, on_change
            )

    async def async_open_1w_port(
        self, address: int, port: int, on_change: Callable[[float | str | None], None]
    ) -> Bmh1wPort:
        """Open and use an 1-Wire port device."""

        async with self._lock:
            return await self.async_io(self.__open_1w_port, address, port, on_change)

    async def async_release(self, resource: BmhResource) -> None:
        """Release a previously opened device."""

        _LOGGER.debug("Releasing device port '%s'", resource.device_port)

        async with self._lock:
            self._resources.pop(resource.device_port)
            close = len(self._resources) == 0

        if close:
            await self.async_close()

    def __close(self) -> None:
        self._handle.close()

    async def async_close(self) -> None:
        """Close hub."""

        _LOGGER.info("Closing hub")

        async with BmhHub._instance_lock:
            if BmhHub._instance == self:
                BmhHub._instance = None

        await self.async_io(self.__close)

        self._io_pool.shutdown(wait=False, cancel_futures=False)
