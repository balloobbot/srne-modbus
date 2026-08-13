"""The top-level SRNE device object."""

from __future__ import annotations

from typing import TYPE_CHECKING

from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusConnectionError,
    ModbusError,
)

from .charge_controller import ChargeController
from .device_info import SERIAL_ADDRESS, SERIAL_ADDRESS_FALLBACK, DeviceInformation
from .inverter import Inverter
from .model import SrneComponent, UpdateReport

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

MANUFACTURER = "SRNE Solar"

# Every component attribute a poll refreshes, in read order.
_POLLED = (
    "charge_controller",
    "inverter",
)

# A serial block the device answers for with one of these is simply not there;
# anything else (timeout, busy, dead link) means "not this time" and retries.
_ABSENT = (IllegalDataAddressError, IllegalFunctionError)


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
        self._polled: list[str] | None = None

    async def async_setup(self) -> None:
        """Read the serial number, which cannot change between polls.

        Run by the first :meth:`async_update` if the caller does not run it
        itself. A failure leaves the device unset up, so the next update
        retries rather than latching a serial of ``None`` forever.
        """
        self.serial_number = await self._async_read_serial_number()
        self._polled = list(_POLLED)

    async def async_update(self) -> UpdateReport:
        """Refresh every polled sub-system, one at a time.

        Components are read independently, the way the upstream integration
        reads its blocks: a sub-system whose read fails keeps its previous
        values while the rest still refresh. Listeners fire only after every
        component has been tried, and only on the ones that refreshed. A
        failure of the link itself raises ``ModbusConnectionError`` instead of
        reporting. The first call sets the device up.
        """
        if self._polled is None:
            await self.async_setup()
        assert self._polled is not None  # async_setup() builds it
        updated: set[str] = set()
        failed: dict[str, ModbusError] = {}
        for name in self._polled:
            component: SrneComponent = getattr(self, name)
            try:
                await component.async_update(notify=False)
            except ModbusConnectionError:
                raise
            except ModbusError as err:
                failed[name] = err
            else:
                updated.add(name)
        for name in updated:
            fresh: SrneComponent = getattr(self, name)
            fresh.notify()
        return UpdateReport(updated, failed)

    async def async_read_raw(self) -> dict[str, dict[int, int | bool]]:
        """Every register this device reads, undecoded — for diagnostics.

        The serial blocks come along: a poll never reads them again, and they
        are the first thing an issue report is read for. A polled component
        that refuses raises, since there the error is the point. Setup is not
        needed — the polled set is the same on every SRNE — so this also works
        on a device that never got that far.
        """
        raw = await self._async_read_serial_raw()
        for name in _POLLED:
            component: SrneComponent = getattr(self, name)
            for space, values in (await component.async_read_raw()).items():
                raw.setdefault(space, {}).update(values)
        return {space: dict(sorted(values.items())) for space, values in raw.items()}

    async def _async_read_serial_raw(self) -> dict[str, dict[int, int | bool]]:
        """Both candidate serial blocks, skipping the one this device refuses.

        A device answers at one of the two addresses and refuses the other, so
        unlike in a component read a refusal here is ordinary.
        """
        raw: dict[str, dict[int, int | bool]] = {}
        for address in (SERIAL_ADDRESS, SERIAL_ADDRESS_FALLBACK):
            block = DeviceInformation(self._unit, base_offset=address)
            try:
                read = await block.async_read_raw()
            except _ABSENT:
                continue
            for space, values in read.items():
                raw.setdefault(space, {}).update(values)
        return raw

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
        except _ABSENT:
            return None
        return block.serial_number or None
