"""String utilities for home controller devices."""

from typing import Any

import bmh


class Strings:
    """String utility class."""

    @staticmethod
    def get_address(address: int) -> str:
        """Convert device address to string in format 0xBAA, where B is the bus number AA is the device address in hexadecimal format."""

        return f"0x{address:03X}"

    @staticmethod
    def get_type_address(address: int) -> str:
        """Convert device address to string including device type like IO or 1W."""

        panel = address & bmh.PANEL_MASK
        address_string = Strings.get_address(address)

        if panel == bmh.PANEL_IO:
            return f"IO[{address_string}]"
        if panel == bmh.PANEL_1W:
            return f"1W[{address_string}]"
        return f"Unknown[{address_string}]"

    @staticmethod
    def get_address_port(address: int, port: int) -> str:
        """Convert device address and device port to string."""

        return f"{Strings.get_address(address)}/{port}"

    @staticmethod
    def get_io_input(address: int, port: int) -> str:
        """Convert I/O device address and input port to string."""

        return f"IO Input[{Strings.get_address_port(address, port)}]"

    @staticmethod
    def get_io_output(address: int, port: int) -> str:
        """Convert I/O device address and output port to string."""

        return f"IO Output[{Strings.get_address_port(address, port)}]"

    @staticmethod
    def get_1w_port(address: int, port: int) -> str:
        """Convert 1-Wire device address and port to string."""

        return f"1W Port[{Strings.get_address_port(address, port)}]"

    @staticmethod
    def get_unique_id(address: int, *args: Any) -> str:
        """Build home assistant unique id from device address and other parameters."""

        parts = [f"{address:03X}", *args]
        return ".".join(map(str, parts))
