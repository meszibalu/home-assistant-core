"""Bali Művek Home Controller and Home Assistant glue code."""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Any

import bmh
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .strings import Strings

_LOGGER = logging.getLogger(__name__)
_DOMAIN_LOCK = DOMAIN + ".lock"

bmh.TRACE_MESSAGES = True
# bmh.ERROR_INJECTION_PROBABILITY = 0.05


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
        self,
        hub: BmhHub,
        device_port: BmhDevicePort,
        on_error: Callable[[Exception], None] | None,
    ) -> None:
        """Create the resource."""

        self._hub = hub
        self._device_port = device_port
        self._device: bmh.Device | None = None
        self._on_error = on_error

    @property
    def device_port(self) -> BmhDevicePort:
        """Return the BmhDevicePort object for the resource."""

        return self._device_port

    @property
    def device(self) -> bmh.Device:
        """Return the associated BmhDevice."""

        if self._device is None:
            raise RuntimeError("Device is not opened, call async_open() first")

        return self._device

    @property
    def address(self) -> int:
        """Return the associated device address."""

        return self._device_port.address

    @property
    def port(self) -> int:
        """Return the associated device port."""

        return self._device_port.port

    async def async_open(self) -> None:
        """Open the resource."""

        self._device = await self._hub.async_open(self)

    async def async_release(self) -> None:
        """Release the resource."""

        await self._hub.async_release(self)

    def read(self) -> None:
        """Schedule reading port in the background.

        The result is delegated to the on_change or on_error method.
        """

        self._hub.background_io(self._read)

    @abstractmethod
    def _read(self) -> None:
        pass

    def call_on_error(self, error: Exception) -> None:
        """Call on_error method if an error occurs."""

        callback = self._on_error

        if callback is None:
            self.log_error(error)
        else:
            callback(error)

    def log_error(self, error: Exception) -> None:
        """Logs device specific error at warning level."""

        _LOGGER.warning("Error occurred on '%s'", self.device_port, exc_info=error)


class BmhIoInput(BmhResource):
    """Hub resource implementation for I/O inputs."""

    def __init__(
        self,
        hub: BmhHub,
        device_port: BmhDevicePort,
        invert: bool,
        on_change: Callable[[bool], None],
        on_error: Callable[[Exception], None] | None,
    ) -> None:
        """Create I/O input resource."""

        super().__init__(hub, device_port, on_error)

        self._invert = invert
        self._on_change = on_change

    @property
    def invert(self) -> bool:
        """Return if input is inverted or not."""

        return self._invert

    def _read(self) -> None:
        _LOGGER.debug("Reading '%s'", self.device_port)

        try:
            inputs = self.device.get_inputs()
        except Exception as e:  # noqa: BLE001
            self.call_on_error(e)
            return

        value = inputs & (1 << self.port) != 0
        self.call_on_change(value)

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
        device_port: BmhDevicePort,
        pwm: bool,
        invert: bool,
        on_change: Callable[[int], None],
        on_error: Callable[[Exception], None] | None,
    ) -> None:
        """Create I/O output resource."""

        super().__init__(hub, device_port, on_error)

        self._pwm = pwm
        self._invert = invert
        self._on_change = on_change

    @property
    def pwm(self) -> bool:
        """Return if PWM is enabled for the output or not."""

        return self._pwm

    @property
    def invert(self) -> bool:
        """Return if output is inverted or not."""

        return self._invert

    def _read(self) -> None:
        _LOGGER.debug("Reading '%s'", self.device_port)

        try:
            value = self.device.get_output(self.port)
        except Exception as e:  # noqa: BLE001
            self.call_on_error(e)
            return

        self.call_on_change(value)

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


class Bmh1wPort(BmhResource):
    """Hub resource implementation for 1-Wire ports."""

    def __init__(
        self,
        hub: BmhHub,
        device_port: BmhDevicePort,
        on_change: Callable[[float | None], None],
        on_error: Callable[[Exception], None] | None,
    ) -> None:
        """Create 1-Wire port resource."""

        super().__init__(hub, device_port, on_error)

        self._on_change = on_change

    def _read(self) -> None:
        _LOGGER.debug("Reading '%s'", self.device_port)

        try:
            temperature = self._device.get_temperature(self.port)
        except Exception as e:  # noqa: BLE001
            self.call_on_error(e)
            return

        self.call_on_change(temperature)

    def call_on_change(self, temperature: float | None) -> None:
        """Call on_change method with the new 1-Wire port value."""

        _LOGGER.debug("'%s' changed to '%s'", self.device_port, temperature)

        callback = self._on_change

        if callback is None:
            return

        callback(temperature)


class BmhHub:
    """Bali Művek Home Controller hub for managing devices from Home Assistant."""

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

            # clear reset interrupt
            device.get_reset()

            # clear backup mode interrupt
            if isinstance(device, bmh.DeviceIo):
                device.is_backup_mode()

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

        # happy path
        if DOMAIN in hass.data:
            return hass.data[DOMAIN]

        lock = hass.data.setdefault(_DOMAIN_LOCK, asyncio.Lock())

        async with lock:
            if DOMAIN in hass.data:
                return hass.data[DOMAIN]

            _LOGGER.info("Opening hub")

            hub = BmhHub(hass)
            await hub.async_io(hub.__check_devices)

            hass.data[DOMAIN] = hub

            return hub

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

    def __call_on_change(self, device_port: BmhDevicePort, value: any) -> None:
        if device_port not in self._resources:
            return

        resource = self._resources[device_port]
        resource.call_on_change(value)  # type: ignore[attr-defined]

    def __call_on_error(self, device_port: BmhDevicePort, error: Exception) -> None:
        if device_port not in self._resources:
            return

        resource = self._resources[device_port]
        resource.call_on_error(error)

    def __on_io_input_all_interrupt(self, device: bmh.DeviceIo, status: int) -> None:
        try:
            # we have to read output to clear interrupt
            inputs = device.get_inputs()
        except Exception as e:  # noqa: BLE001
            for port in range(6):
                if status & bmh.DeviceIo.INPUT_INTERRUPT_CHANNEL(port):
                    device_port = BmhDevicePort.get_io_input(device.id, port)
                    self.__call_on_error(device_port, e)

            return

        for port in range(6):
            if status & bmh.DeviceIo.INPUT_INTERRUPT_CHANNEL(port):
                device_port = BmhDevicePort.get_io_input(device.id, port)
                value = bool(inputs & (1 << port))

                self.__call_on_change(device_port, value)

    def __on_io_output_port_interrupt(self, device: bmh.DeviceIo, port: int) -> None:
        device_port = BmhDevicePort.get_io_output(device.id, port)

        try:
            # we have to read output to clear interrupt
            value = device.get_output(port)
        except Exception as e:  # noqa: BLE001
            self.__call_on_error(device_port, e)
            return

        self.__call_on_change(device_port, value)

    def __on_io_backup_mode_interrupt(self, device: bmh.DeviceIo) -> None:
        device_string = Strings.get_type_address(device.id)

        try:
            backup_mode = device.is_backup_mode()
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning(
                "Could not get device '%s' reset reason", device_string, exc_info=e
            )
            backup_mode = "UNKNOWN"

        self.notify(
            "Backup mode",
            f"Device '{device_string}' changed backup mode: {backup_mode}",
        )

    def __on_io_interrupt(self, device: bmh.DeviceIo, status: int) -> int:
        handled = 0

        if status & bmh.DeviceIo.INPUT_INTERRUPT_CHANNELS:
            self.__on_io_input_all_interrupt(device, status)
            handled |= bmh.DeviceIo.INPUT_INTERRUPT_CHANNELS

        if status & bmh.DeviceIo.OUTPUT_INTERRUPT_CHANNELS:
            for port in range(6):
                if status & bmh.DeviceIo.OUTPUT_INTERRUPT_CHANNEL(port):
                    self.__on_io_output_port_interrupt(device, port)

            handled |= bmh.DeviceIo.OUTPUT_INTERRUPT_CHANNELS

        if status & bmh.DeviceIo.BACKUP_MODE_INTERRUPT_CHANNEL:
            self.__on_io_backup_mode_interrupt(device)
            handled |= bmh.DeviceIo.BACKUP_MODE_INTERRUPT_CHANNEL

        return handled

    def __on_1w_port_interrupt(self, device: bmh.Device1w, port: int) -> None:
        device_port = BmhDevicePort.get_1w_port(device.id, port)

        try:
            # we have to read temperature to clear interrupt
            temperature = device.get_temperature(port)
        except Exception as e:  # noqa: BLE001
            self.__call_on_error(device_port, e)
            return

        self.__call_on_change(device_port, temperature)

    def __on_1w_interrupt(self, device: bmh.Device1w, status: int) -> int:
        for port in range(10):
            if status & bmh.Device1w.PORT_INTERRUPT_CHANNEL(port):
                self.__on_1w_port_interrupt(device, port)

        return bmh.Device1w.PORT_INTERRUPT_CHANNELS

    def __on_reset_interrupt(self, device: bmh.Device) -> None:
        device_string = Strings.get_address(device.id)

        try:
            reset = device.get_reset()
            reason = reset.name
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning(
                "Could not get device '%s' reset reason", device_string, exc_info=e
            )
            reason = "UNKNOWN"

        self.notify("Reset", f"Device '{device_string}' was reset: {reason}")

        if device.version != bmh.VERSION:
            self.notify(
                "Version mismatch",
                f"Device '{device_string}' ({device.version}) "
                "does not have the most recent version "
                f"({bmh.VERSION})",
            )

    def __on_interrupt(self, device: bmh.Device, status: int) -> None:
        handled = 0

        match device:
            case bmh.DeviceIo():
                handled |= self.__on_io_interrupt(device, status)
            case bmh.Device1w():
                handled |= self.__on_1w_interrupt(device, status)

        if status & bmh.Device.RESET_INTERRUPT_CHANNEL:
            self.__on_reset_interrupt(device)
            handled |= bmh.Device.RESET_INTERRUPT_CHANNEL

        not_handled = status & ~handled

        # A device with unhandled interrupt channel will appear in every
        # interrupt search which might slow down interrupt handling
        # and response time.
        if not_handled != 0:
            device_string = Strings.get_address(device.id)

            _LOGGER.warning(
                "Device '%s' has unhandled interrupts '0x%04X'",
                device_string,
                not_handled,
            )

    def create_io_input(
        self,
        address: int,
        port: int,
        invert: bool,
        on_change: Callable[[bool], None],
        on_error: Callable[[Exception], None] | None,
    ) -> BmhIoInput:
        """Create a device for an I/O input.

        The device must be opened before usage.
        """

        device_port = BmhDevicePort.get_io_input(address, port)

        return BmhIoInput(self, device_port, invert, on_change, on_error)

    def create_io_output(
        self,
        address: int,
        port: int,
        pwm: bool,
        invert: bool,
        on_change: Callable[[int], None],
        on_error: Callable[[Exception], None] | None,
    ) -> BmhIoOutput:
        """Create a device for an I/O output.

        The device must be opened before usage.
        """

        device_port = BmhDevicePort.get_io_output(address, port)

        return BmhIoOutput(self, device_port, pwm, invert, on_change, on_error)

    def create_1w_port(
        self,
        address: int,
        port: int,
        on_change: Callable[[float | None], None],
        on_error: Callable[[Exception], None] | None,
    ) -> Bmh1wPort:
        """Create a device for a 1-Wire port.

        The device must be opened before usage.
        """

        device_port = BmhDevicePort.get_1w_port(address, port)

        return Bmh1wPort(self, device_port, on_change, on_error)

    def __open(self, resource: BmhResource) -> bmh.Device:
        _LOGGER.debug("Using device port '%s'", resource.device_port)

        self.__check_device_port_available(resource.device_port)
        device = self._handle.get_device(resource.address)

        self._resources[resource.device_port] = resource

        bus = device.bus

        if bus.interrupt_handler is None:
            bus.interrupt_handler = self.__on_interrupt

        return device

    async def async_open(self, resource: BmhResource) -> bmh.Device:
        """Open a device."""

        async with self._lock:
            return await self.async_io(self.__open, resource)

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

        lock = self._hass.data.get(_DOMAIN_LOCK)

        if lock is None:
            return

        async with lock:
            self._hass.data.pop(DOMAIN)
            self._hass.data.pop(_DOMAIN_LOCK)

        await self.async_io(self.__close)

        self._io_pool.shutdown(wait=False, cancel_futures=False)
