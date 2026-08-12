"""The top-level SRNE device object."""

from __future__ import annotations

from typing import TYPE_CHECKING

from modbus_connection import ModbusError
from modbus_connection.model import ComponentGroup

from .charge_controller import ChargeController
from .device_info import SERIAL_ADDRESS, SERIAL_ADDRESS_FALLBACK, DeviceInformation
from .inverter import Inverter

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

MANUFACTURER = "SRNE Solar"


def _swap_byte_pairs(text: str) -> str:
    """Swap adjacent characters; a trailing odd character stays put."""
    pairs = [text[i : i + 2] for i in range(0, len(text), 2)]
    return "".join(pair[::-1] if len(pair) == 2 else pair for pair in pairs)


class SrneInverter:
    """An SRNE Solar hybrid inverter / charge controller.

    Takes a :class:`~modbus_connection.ModbusUnit`; the caller owns the
    connection. ASCII framing is not supported — see the README.
    """

    manufacturer = MANUFACTURER

    def __init__(self, unit: ModbusUnit) -> None:
        self._unit = unit
        self.charge_controller = ChargeController(unit)
        self.inverter = Inverter(unit)
        self.serial_number: str | None = None
        self._group = ComponentGroup(unit, [self.charge_controller, self.inverter])
        self._setup_done = False

    async def async_setup(self) -> None:
        """Read the serial number, which cannot change between polls."""
        self.serial_number = await self._async_read_serial_number()
        self._setup_done = True

    async def async_update(self) -> None:
        """Refresh every polled measurement; the first call sets the device up."""
        if not self._setup_done:
            await self.async_setup()
        await self._group.async_update()

    async def _async_read_serial_number(self) -> str | None:
        """Try the primary block, then the fallback one.

        Upstream reports the fallback block byte-swapped on inverters whose
        serial does not begin with ``M`` or ``X``; that correction is kept.
        """
        serial = await self._async_read_serial_at(SERIAL_ADDRESS)
        if serial:
            return serial

        serial = await self._async_read_serial_at(SERIAL_ADDRESS_FALLBACK)
        if serial and not serial.startswith(("M", "X")):
            return _swap_byte_pairs(serial)
        return serial

    async def _async_read_serial_at(self, address: int) -> str | None:
        block = DeviceInformation(self._unit, base_offset=address)
        try:
            await block.async_update()
        except ModbusError:
            return None
        return block.serial_number or None
